"""Host-owned actual native ABORT/CLOSE and outcome fixtures.

A passing cohort proves these bounded original-native operations, not arbitrary
child/thread settlement, worker reuse, positive prompt answers, or v0.8 release.
"""

from contextlib import closing
import json
import sqlite3

CASES = ("abort-paused", "abort-running", "abort-prompt", "normal", "error", "timeout")


def prepare_terminal_fixtures(sources):
    entered = "from pathlib import Path\nPath('/workspace/terminal-entered').write_text('entered')\n"
    loop = "import time\nwhile True:\n    time.sleep(0.02)\n"
    prompt = (
        "from spell.lang.functions import Prompt\n"
        "from spell.lang.constants import LIST\n"
        "answer=Prompt('V08_TERMINAL_FIXTURE',['A :First','B :Second'],Type=LIST,"
    )
    bodies = {
        "abort-paused": entered
        + "Path('/workspace/terminal-result').write_text('unsafe')\n",
        "abort-running": entered
        + loop
        + "Path('/workspace/terminal-result').write_text('unsafe')\n",
        "abort-prompt": entered
        + prompt
        + "Default='A',Timeout=0,HandleError=False)\nPath('/workspace/terminal-result').write_text(answer)\n",
        "normal": entered + "Path('/workspace/terminal-result').write_text('normal')\n",
        "error": entered
        + "raise RuntimeError('V08_EXPECTED_TERMINAL_ERROR')\nPath('/workspace/terminal-result').write_text('unsafe')\n",
        "timeout": entered
        + prompt
        + "Default='B',Timeout=0.3,HandleError=False)\nPath('/workspace/terminal-result').write_text(answer)\n",
    }
    for name, body in bodies.items():
        (sources / ("terminal_" + name.replace("-", "_") + ".py")).write_text(body)


def qualify_terminal_controls(
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
    if case not in CASES:
        raise ValueError("Unknown terminal case")
    await_event([name], "native-terminal-ready", seconds=45)
    before = controller("execution.list", {})
    unrelated = [row for row in before["executions"] if row["id"] != execution["id"]]
    proof = dict(
        execution_id=execution["id"],
        connection_id=connection,
        expected_epoch=execution["epoch"],
        connection_generation=execution["connection_generation"],
        capability=execution["capability"],
        target_admission_id=None,
    )
    issued = []

    def issue(native_command):
        result = controller("execution.command", dict(proof, command=native_command))
        if (
            result["runtime_enabled"] is not False
            or result["effective_transfer"] is not False
        ):
            raise RuntimeError("Terminal action promoted runtime or transfer authority")
        issued.append((result["command_id"], native_command))

    if case != "abort-paused":
        issue("CMD_RUN")
    if case in {"abort-running", "abort-prompt"}:
        await_event([name], "native-terminal-intermediate", seconds=30)
    if case.startswith("abort-"):
        issue("CMD_ABORT")
    await_event([name], "native-terminal-outcome", seconds=35)
    issue("CMD_CLOSE")
    await_event([name], "native-terminal-close-exited", seconds=25)
    if command("docker", "wait", name, timeout=20) != "0":
        raise RuntimeError("Native terminal worker cleanup failed")
    info = json.loads(command("docker", "inspect", name))[0]
    if (
        info["State"]["Running"]
        or info["State"]["OOMKilled"]
        or info["State"]["Pid"] != 0
        or info["State"]["ExitCode"] != 0
        or info["Image"] != worker_image
    ):
        raise RuntimeError("Native terminal worker exit identity/outcome differs")
    # Kernel container exit is checked independently of the worker's pidfd event.
    # Context and native Listener may need supervisor teardown; the Executor must
    # have exited via owner CLOSE BEFORE that cleanup, as separately asserted.
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        actual = db.execute(
            "SELECT command_id,command,state FROM native_owner_commands ORDER BY sequence"
        ).fetchall()
        if actual != [
            (identity, native_command, "EXECUTION_UNPROVEN")
            for identity, native_command in issued
        ]:
            raise RuntimeError(
                "Native terminal command journal differs from actual consumed actions"
            )
        if (
            db.execute("SELECT COUNT(*) FROM native_control_attempts").fetchone()[0]
            != 0
        ):
            raise RuntimeError("Native terminal fixture used a startup RUN grant")
        if db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 2:
            raise RuntimeError("Native terminal fixture released uncertain holds")
        if db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1:
            raise RuntimeError("Native terminal fixture reused a worker")
        if db.execute(
            "SELECT owner,epoch,control_state FROM executions WHERE id=?",
            (execution["id"],),
        ).fetchone() != ("alice", execution["epoch"], "OWNED"):
            raise RuntimeError("Native terminal fixture changed ownership")
    after = controller("execution.list", {})
    if unrelated != [
        row for row in after["executions"] if row["id"] != execution["id"]
    ]:
        raise RuntimeError("Native terminal action modified an unrelated witness")
    records = events(name)
    outcomes = [row for row in records if row["event"] == "native-terminal-outcome"]
    exits = [row for row in records if row["event"] == "native-terminal-close-exited"]
    expected = (
        "ABORTED"
        if case.startswith("abort-")
        else "ERROR"
        if case == "error"
        else "FINISHED"
    )
    if (
        len(outcomes) != 1
        or outcomes[0]["native_status"] != expected
        or len(exits) != 1
    ):
        raise RuntimeError("Native terminal observations are missing or duplicated")
    if sum(row["event"] == "native-before-consume-admitted" for row in records) != len(
        issued
    ):
        raise RuntimeError("Native terminal action bypassed final consumption")
    report.setdefault("native_terminal_cases", {})[case] = dict(
        passed=True,
        commands=[cmd for _, cmd in issued],
        native_outcome=expected,
        actual_native_executor=True,
        original_executor_exit_observed=True,
        host_teardown_used_for_executor=False,
        container_exit_verified=True,
        unrelated_witness_unchanged=True,
        holds_retained=2,
        spent_workers_retained=1,
        effects_settled=False,
        full_step1_qualified=False,
        full_v08_qualified=False,
    )
