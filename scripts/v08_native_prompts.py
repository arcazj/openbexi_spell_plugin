"""Real native root/child answer, default, cancel and disconnected-owner probes."""

from contextlib import closing
import json
import sqlite3
import time
import uuid

from openbexi_spell_server.contracts import Fault


def select_pending_prompt(
    db, execution_id, *, instance=None, child_entrypoint=None, exclude=()
):
    """Select only an exact originally bound member, never a guessed child suffix."""
    if (instance is None) == (child_entrypoint is None):
        raise ValueError("Choose one exact root or admitted child prompt scope")
    query = (
        "SELECT p.* FROM native_prompts p JOIN native_members m "
        "ON p.execution_id=m.execution_id AND p.target_id=m.target_id "
        "AND p.instance_id=m.instance_id AND p.origin_hash=m.origin_hash "
        "AND p.member_hash=m.binding_hash "
    )
    parameters = [execution_id]
    if child_entrypoint is not None:
        query += (
            "JOIN child_admissions c ON c.id=p.target_id "
            "AND c.execution_id=p.execution_id AND c.origin_hash=p.origin_hash "
            "AND c.parent_id IS NULL AND c.state='CONSUMED' "
        )
    query += (
        "WHERE p.execution_id=? AND p.state='OPEN' AND m.state='REGISTERED_UNPROVEN' "
    )
    if child_entrypoint is not None:
        query += "AND c.entrypoint=?"
        parameters.append(child_entrypoint)
    else:
        query += "AND p.target_id='' AND p.instance_id=?"
        parameters.append(instance)
    rows = db.execute(query, parameters).fetchall()
    selected = [dict(row) for row in rows if row["prompt_id"] not in exclude]
    if len(selected) > 1:
        raise RuntimeError("Original native member scope has multiple pending prompts")
    return selected[0] if selected else None


def pending_prompt(
    state, execution_id, *, instance=None, child_entrypoint=None, exclude=(), seconds=25
):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with closing(
            sqlite3.connect(
                "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
            )
        ) as db:
            db.row_factory = sqlite3.Row
            selected = select_pending_prompt(
                db,
                execution_id,
                instance=instance,
                child_entrypoint=child_entrypoint,
                exclude=exclude,
            )
            if selected is not None:
                return selected
        time.sleep(0.03)
    raise TimeoutError("Original native prompt registration not observed")


def qualify_prompt_execution(
    *,
    name,
    execution,
    connection,
    controller,
    control,
    state,
    worker_image,
    command,
    await_event,
    host_processes,
    events,
    report,
    mode,
):
    await_event([name], "native-prompt-ready", seconds=45)
    original_pids = host_processes(name)
    proof = dict(
        execution_id=execution["id"],
        connection_id=connection,
        expected_epoch=execution["epoch"],
        connection_generation=execution["connection_generation"],
        capability=execution["capability"],
    )
    controller(
        "execution.command", dict(proof, target_admission_id=None, command="CMD_RUN")
    )
    prefix = "prompt_" + mode
    registered = []

    def reply(prompt, action, value):
        return dict(
            proof,
            prompt_id=prompt["prompt_id"],
            target_admission_id=prompt["target_id"] or None,
            definition_sha256=prompt["definition_hash"],
            action=action,
            answer=value,
        )

    def denied(payload, subject="alice"):
        try:
            controller("execution.prompt.reply", payload, subject=subject)
        except Fault as fault:
            if fault.status not in (400, 403, 409):
                raise RuntimeError("Native prompt rejection status differs") from fault
        else:
            raise RuntimeError("Foreign or retargeted native prompt reply was admitted")

    prompt = pending_prompt(state, execution["id"], instance=prefix + "#1")
    registered.append(prompt["prompt_id"])
    await_event([name], "native-prompt-denial-observed", minimum=1, seconds=10)
    payload = reply(prompt, "ANSWER", "approved")
    denied(payload, subject="bob")
    denied(dict(payload, definition_sha256="0" * 64))
    denied(dict(payload, target_admission_id=str(uuid.uuid4())))
    if mode == "complete":
        controller("execution.prompt.reply", payload)
        child = pending_prompt(
            state, execution["id"], child_entrypoint="prompt_child.py"
        )
        if not child["target_id"]:
            raise RuntimeError(
                "Native child prompt lost its independent admission identity"
            )
        registered.append(child["prompt_id"])
        await_event([name], "native-prompt-denial-observed", minimum=2, seconds=10)
        denied(dict(reply(child, "ANSWER", "42"), target_admission_id=None))
        denied(payload)  # Closed-generation replay cannot be newly admitted.
        controller("execution.prompt.reply", reply(child, "ANSWER", "42"))
        second = pending_prompt(
            state, execution["id"], instance=prefix + "#1", exclude=registered
        )
        registered.append(second["prompt_id"])
        await_event([name], "native-prompt-denial-observed", minimum=3, seconds=10)
        controller("execution.prompt.reply", reply(second, "ANSWER", "next"))
        await_event([name], "native-prompt-finished", seconds=30)
    elif mode == "cancel":
        controller("execution.prompt.reply", reply(prompt, "CANCEL", None))
        await_event([name], "native-prompt-finished", seconds=30)
    else:
        controller("execution.prompt.reply", payload)
        deadline = time.monotonic() + 8
        while True:
            output = command(
                "docker",
                "exec",
                name,
                "python",
                "-I",
                "-c",
                "from pathlib import Path;print(Path('/workspace/prompt-awaiting').exists())",
            )
            if output.strip() == "True":
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Native prompt did not reach final-consumption barrier"
                )
            time.sleep(0.05)
        controller("session.close", {"connection_id": connection})
        (control / "prompt-release").write_text(
            "owner disconnected before final consumption\n"
        )
        await_event([name], "native-prompt-consume-fenced", seconds=8)
        time.sleep(0.5)
        command(
            "docker",
            "exec",
            name,
            "python",
            "-I",
            "-c",
            "from pathlib import Path;assert not Path('/workspace/prompt-UNSAFE').exists()",
        )
        if {x["host_pid"] for x in host_processes(name)} != {
            x["host_pid"] for x in original_pids
        }:
            raise RuntimeError(
                "Fenced prompt substituted an original native participant"
            )
        (control / "prompt-observed").write_text("host verified no subsequent effect\n")
        await_event([name], "native-prompt-fenced-held", seconds=10)
    if command("docker", "wait", name, timeout=20) != "0":
        raise RuntimeError("Native prompt qualification worker failed")
    info = json.loads(command("docker", "inspect", name))[0]
    if (
        info["State"]["Running"]
        or info["State"]["OOMKilled"]
        or info["Image"] != worker_image
        or info["HostConfig"]["Privileged"]
        or not info["HostConfig"]["ReadonlyRootfs"]
    ):
        raise RuntimeError("Native prompt worker isolation or termination differs")
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        outcomes = db.execute(
            "SELECT state,outcome FROM native_prompts ORDER BY rowid"
        ).fetchall()
        expected = (
            [("CLOSED", "ANSWER_SELECTED")] * 3 + [("CLOSED", "DEFAULT_SELECTED")]
            if mode == "complete"
            else [("CLOSED", "CANCEL_SELECTED")]
            if mode == "cancel"
            else [("OPEN", None)]
        )
        if outcomes != expected:
            raise RuntimeError(
                "Native prompt durable outcomes differ: " + repr(outcomes)
            )
        reply_states = db.execute(
            "SELECT state FROM native_prompt_replies ORDER BY sequence"
        ).fetchall()
        expected_replies = [("CONSUMED_UNPROVEN",)] * (3 if mode == "complete" else 1)
        if mode == "fenced":
            expected_replies = [("FORWARD_UNPROVEN",)]
        if reply_states != expected_replies:
            raise RuntimeError(
                "Native prompt reply origins or final consumption differ"
            )
        holds = 3 if mode == "complete" else 2
        if (
            db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != holds
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1
        ):
            raise RuntimeError(
                "Prompt result released uncertain holds or reused a worker"
            )
        owner = db.execute(
            "SELECT owner,epoch,control_state FROM executions WHERE id=?",
            (execution["id"],),
        ).fetchone()
        if owner != (
            "alice",
            execution["epoch"],
            "CONTROLLER_DISCONNECTED" if mode == "fenced" else "OWNED",
        ):
            raise RuntimeError("Prompt operation changed owner or authority epoch")
    records = events(name)
    close_count = sum(
        x.get("phase") == "openbexi.native-prompt-close/1" for x in records
    )
    if close_count != (4 if mode == "complete" else 1 if mode == "cancel" else 0):
        raise RuntimeError(
            "Original native close callbacks differ from Context outcomes"
        )
    report["native_prompt_" + mode] = dict(
        passed=True,
        actual_native_executor=True,
        actual_child=mode == "complete",
        outcomes=[state for _, state in outcomes],
        final_owner_check_rejected=mode == "fenced",
        native_close_callbacks=close_count,
        holds_retained=holds,
        worker_single_use=True,
        host_cleanup_only=True,
        safe_operational_cleanup_proven=False,
        runtime_enabled=False,
        full_step1_qualified=False,
        full_v08_qualified=False,
    )
