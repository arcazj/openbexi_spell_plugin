"""Host-owned terminal acceptance and process cleanup; no reservation reuse."""

from contextlib import closing
import json
import os
import select
import sqlite3

from openbexi_spell_server.contracts import Fault

CASES = (
    "forced-loss",
    "close-wait",
    "close-child",
    "abort-paused",
    "close-paused",
    "abort-running",
    "close-running",
    "abort-prompt",
    "close-prompt",
    "cancel-prompt",
    "normal",
    "error",
    "timeout",
    "abort-thread",
    "abort-child",
    "close-thread",
)


def terminal_fixture(case):
    from v08_prompt_cohort import prompt_fixture

    if "prompt" in case:
        return prompt_fixture()
    if case == "timeout":
        return prompt_fixture(timeout=True)
    if case == "normal":
        return "RESULT = 42\nassert RESULT == 42\n"
    if case == "error":
        return "raise RuntimeError('expected native terminal fixture failure')\n"
    if case == "close-wait":
        return (
            "from spell.lang.functions import WaitFor\n"
            "WaitFor(120)\n"
            "raise AssertionError('CLOSE did not interrupt the native scheduler wait')\n"
        )
    if case.endswith("-child"):
        return (
            "from spell.lang.functions import StartProc\n"
            "StartProc('terminal_child',Automatic=True,Visible=True,Blocking=True,HandleError=False)\n"
        )
    prefix = "import time,threading\n"
    if case.endswith("-thread"):
        prefix += (
            "def background():\n"
            "    while True:time.sleep(0.05)\n"
            "threading.Thread(target=background,daemon=True).start()\n"
        )
    return prefix + (
        "with open('/workspace/terminal-active','w') as f:f.write('active')\n"
        "while True:time.sleep(0.05)\n"
    )


def capture_process_handles(command, name):
    # pidfds cannot silently become proofs about recycled numeric PIDs.
    rows = command("docker", "top", name, "-eo", "pid").splitlines()[1:]
    handles = []
    try:
        for row in rows:
            handles.append(os.pidfd_open(int(row.strip())))
    except BaseException:
        for handle in handles:
            os.close(handle)
        raise
    return handles


def direct_child_target(db, execution_id):
    children = db.execute(
        "SELECT a.id FROM child_admissions a JOIN native_members m "
        "ON m.execution_id=a.execution_id AND m.target_id=a.id "
        "WHERE a.execution_id=? AND a.parent_id IS NULL AND a.state='CONSUMED' "
        "AND m.state='REGISTERED_UNPROVEN'",
        (execution_id,),
    ).fetchall()
    if len(children) != 1:
        raise RuntimeError(
            "Native CLOSE child has no unique consumed registered admission"
        )
    return children[0][0]


def validate_stopped(info, container_id, image):
    if (
        info["Id"] != container_id
        or info["Image"] != image
        or info["State"]["Running"]
        or info["State"]["Pid"] != 0
        or info["State"]["OOMKilled"]
        or info["State"]["ExitCode"] != 0
    ):
        raise RuntimeError("Terminal container identity or clean exit differs")


def retire_terminal_probe(
    command, output, worker, context, probe_networks, names, networks
):
    # Run only after native cleanup and durable holds were independently checked.
    # Each case keeps its own fresh Context, but completed cases must not consume
    # the Docker daemon's finite default address pools for the rest of the cohort.
    command("docker", "stop", "--time", "5", context)
    for name in (worker, context):
        info = json.loads(command("docker", "inspect", name))[0]
        if info["State"]["Running"] or info["State"]["Pid"] != 0:
            raise RuntimeError("Completed terminal probe still has a live container")
        (output / (name + ".state.json")).write_text(
            json.dumps(
                dict(
                    id=info["Id"],
                    state=info["State"],
                    image=info["Image"],
                    memory_limit=info["HostConfig"]["Memory"],
                    readonly_root=info["HostConfig"]["ReadonlyRootfs"],
                ),
                indent=2,
            )
            + "\n"
        )
        (output / (name + ".stdout.jsonl")).write_text(
            command("docker", "logs", name) + "\n"
        )
    # No force removal: an unexpected live process makes qualification fail.
    command("docker", "rm", worker, context)
    names.remove(worker)
    names.remove(context)
    for network in probe_networks:
        command("docker", "network", "rm", network)
        networks.remove(network)


def qualify_terminal_case(
    *,
    case,
    name,
    execution,
    connection,
    controller,
    state,
    worker_image,
    command,
    control,
    await_event,
    events,
    report,
    host_call,
):
    await_event([name], "native-terminal-ready", seconds=45)
    before = json.loads(command("docker", "inspect", name))[0]
    handles = capture_process_handles(command, name)
    proof = dict(
        execution_id=execution["id"],
        connection_id=connection,
        expected_epoch=execution["epoch"],
        connection_generation=execution["connection_generation"],
        capability=execution["capability"],
        target_admission_id=None,
    )
    commands = []
    try:
        for replacement in (dict(capability="0" * 64), dict(expected_epoch=2)):
            try:
                controller(
                    "execution.command", dict(proof, command="CMD_ABORT", **replacement)
                )
            except Fault as error:
                if error.status != 403:
                    raise
            else:
                raise RuntimeError("Terminal stale/forged owner was admitted")
        if not case.endswith("paused"):
            commands.append(
                controller("execution.command", dict(proof, command="CMD_RUN"))[
                    "command_id"
                ]
            )
        if case == "forced-loss":
            await_event([name], "native-terminal-active", seconds=25)
            handles.extend(capture_process_handles(command, name))
            (control / "kill-native").write_text("x")
        if case not in {"normal", "error", "timeout", "forced-loss"}:
            if not case.endswith("paused"):
                await_event([name], "native-terminal-active", seconds=25)
                # Include descendants and background threads' owning processes.
                handles.extend(capture_process_handles(command, name))
            if case == "cancel-prompt":
                with closing(sqlite3.connect(state / "context.sqlite3")) as db:
                    prompt = db.execute(
                        "SELECT prompt_id,definition_hash FROM native_prompts WHERE state='OPEN'"
                    ).fetchone()
                if prompt is None:
                    raise RuntimeError("Native CANCEL has no actual pending prompt")
                controller(
                    "execution.prompt.reply",
                    dict(
                        proof,
                        prompt_id=prompt[0],
                        definition_sha256=prompt[1],
                        action="CANCEL",
                        answer=None,
                    ),
                )
            else:
                if case == "close-child":
                    # Each member needs its own owner grant. Close the child
                    # first so a completed root cannot outrun child dispatch.
                    with closing(sqlite3.connect(state / "context.sqlite3")) as db:
                        target = direct_child_target(db, execution["id"])
                    commands.append(
                        controller(
                            "execution.command",
                            dict(
                                proof, command="CMD_CLOSE", target_admission_id=target
                            ),
                        )["command_id"]
                    )
                native_command = (
                    "CMD_CLOSE" if case.startswith("close-") else "CMD_ABORT"
                )
                commands.append(
                    controller(
                        "execution.command", dict(proof, command=native_command)
                    )["command_id"]
                )
        await_event([name], "native-terminal-observed", seconds=30)
        observed = [
            row for row in events(name) if row["event"] == "native-terminal-observed"
        ]
        if len(observed) != 1:
            raise RuntimeError("Native terminal outcome is ambiguous")
        fence = host_call(
            "begin",
            container_id=before["Id"],
            native_status=observed[0]["native_status"],
        )
        if fence["state"] != "FENCED" or fence["hold_retained"] is not True:
            raise RuntimeError("Host did not obtain a durable terminal fence")
        (control / "terminal-cleanup").write_text("x")
        if command("docker", "wait", name, timeout=20) != "0":
            raise RuntimeError("Native terminal worker cleanup failed")
        after = json.loads(command("docker", "inspect", name))[0]
        validate_stopped(after, before["Id"], worker_image)
        if any(not select.select([handle], [], [], 0)[0] for handle in handles):
            raise RuntimeError("Original terminal participant survived container exit")
        observed = [
            row for row in events(name) if row["event"] == "native-terminal-observed"
        ]
        expected = (
            "UNKNOWN"
            if case == "forced-loss"
            else "CLOSED"
            if case.startswith("close-")
            else "ERROR"
            if case == "error"
            else "FINISHED"
            if case in {"normal", "timeout"}
            else "ABORTED"
        )
        if (
            len(observed) != 1
            or observed[0]["native_status"] != expected
            or observed[0]["pending_prompts"]
        ):
            raise RuntimeError("Native terminal outcome or prompt cleanup differs")
        with closing(sqlite3.connect(state / "context.sqlite3")) as db:
            rows = db.execute(
                "SELECT command_id,state FROM native_owner_commands ORDER BY sequence"
            ).fetchall()
            if rows != [(value, "EXECUTION_UNPROVEN") for value in commands]:
                raise RuntimeError("Native terminal durable consumption differs")
            prompts = db.execute("SELECT state,outcome FROM native_prompts").fetchall()
            expected_prompt = (
                "CANCEL_SELECTED"
                if case == "cancel-prompt"
                else "TERMINAL_CANCELLED"
                if "prompt" in case
                else "TIMEOUT"
                if case == "timeout"
                else None
            )
            if prompts != (
                [] if expected_prompt is None else [("CLOSED", expected_prompt)]
            ):
                raise RuntimeError("Native prompt terminal outcome is unresolved")
            holds = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            if (
                holds < 2
                or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1
            ):
                raise RuntimeError(
                    "Terminal cleanup reused a worker or released a hold"
                )
        evidence = dict(
            provider="docker-pidfd-terminal/1",
            container_id=after["Id"],
            image=after["Image"],
            running=after["State"]["Running"],
            pid=after["State"]["Pid"],
            exit_code=after["State"]["ExitCode"],
            oom_killed=after["State"]["OOMKilled"],
            restart_count=after["RestartCount"],
            original_handles=len(handles),
            exited_handles=len(handles),
            roster_hash=fence["roster_hash"],
        )
        settled = host_call("complete", challenge=fence["challenge"], evidence=evidence)
        expected_settlement = "HELD" if case == "forced-loss" else "SETTLED"
        if settled["state"] != expected_settlement:
            raise RuntimeError("Terminal settlement differs: " + json.dumps(settled))
        if (
            host_call("complete", challenge=fence["challenge"], evidence=evidence)
            != settled
        ):
            raise RuntimeError("Terminal evidence replay changed its result")
        if case == "forced-loss":
            try:
                host_call(
                    "release",
                    challenge=fence["challenge"],
                    report_hash=settled["report_hash"],
                )
            except Fault as error:
                if error.status != 409:
                    raise
            else:
                raise RuntimeError("Unknown native loss released reservations")
        else:
            released = host_call(
                "release",
                challenge=fence["challenge"],
                report_hash=settled["report_hash"],
            )
            if (
                released["state"] != "RELEASED"
                or released["worker_reusable"] is not False
            ):
                raise RuntimeError("Proven terminal reservation release differs")
        with closing(sqlite3.connect(state / "context.sqlite3")) as db:
            remaining = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            own = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE execution_id=?",
                (execution["id"],),
            ).fetchone()[0]
            if (
                own != (holds - 1 if case == "forced-loss" else 0)
                or remaining != own + 1
            ):
                raise RuntimeError("Terminal settlement changed unrelated holds")
            if db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1:
                raise RuntimeError("Terminal settlement recycled a spent worker")
        report.setdefault("native_terminal_cases", []).append(
            dict(
                case=case,
                passed=True,
                native_status=expected,
                actual_native_executor=True,
                consumed_owner_commands=len(commands),
                prompt_outcomes=prompts,
                original_process_handles_exited=len(handles),
                container_id=before["Id"],
                whole_container_terminated=True,
                pending_prompts=0,
                logical_holds_before_settlement=holds,
                logical_holds_retained=remaining,
                terminal_settlement=settled,
                reservation_released=case != "forced-loss",
                worker_spent=True,
                unknown_effects_replayable=False,
                quiescence_proven=False,
                effective_transfer=False,
                runtime_enabled=False,
            )
        )
    finally:
        for handle in handles:
            os.close(handle)
