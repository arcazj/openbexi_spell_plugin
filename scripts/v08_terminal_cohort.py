"""Host-owned terminal acceptance and process cleanup; no reservation reuse."""

from contextlib import closing
import json
import os
import select
import sqlite3

from openbexi_spell_server.contracts import Fault

CASES = (
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
    if case == "abort-child":
        return (
            "from spell.lang.functions import StartProc\n"
            "StartProc('terminal_child',Automatic=True,Visible=True,Blocking=True,HandleError=False)\n"
        )
    prefix = "import time,threading\n"
    if case == "abort-thread":
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
    await_event,
    events,
    report,
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
        if case not in {"normal", "error", "timeout"}:
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
                native_command = (
                    "CMD_CLOSE" if case.startswith("close-") else "CMD_ABORT"
                )
                commands.append(
                    controller(
                        "execution.command", dict(proof, command=native_command)
                    )["command_id"]
                )
        await_event([name], "native-terminal-observed", seconds=30)
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
            "CLOSED"
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
                logical_holds_retained=holds,
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
