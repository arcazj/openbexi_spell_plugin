"""Host-owned stale RUN and fresh owner STEP probes against the native Executor.

The fresh worker has its own slot, certificate, connection, execution and network.
No authority/container introspection is delegated to the Context or worker.
"""

from contextlib import closing
import json
import os
import socket
import uuid
import shutil
import sqlite3
import time

from openbexi_spell_server.contracts import canonical, envelope
from openbexi_spell_server.transport import Route, tls_context
from openbexi_spell_server.worker import preflight


def isolate_audit_probe(config):
    result = dict(config)
    result.pop("native_driver", None)
    result["approved_sources"] = {
        name: dict(entry, driver_binding="context-audit")
        for name, entry in config["approved_sources"].items()
    }
    return result


def qualify_owner_resume(
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
):
    """Actual same-owner RUN/PAUSE/RUN; never positive ownership transfer."""
    await_event([name], "native-owner-resume-ready", seconds=45)
    before = host_processes(name)
    proof = dict(
        execution_id=execution["id"],
        connection_id=connection,
        expected_epoch=execution["epoch"],
        connection_generation=execution["connection_generation"],
        capability=execution["capability"],
        target_admission_id=None,
    )
    unrelated = [
        row
        for row in controller("execution.list", {})["executions"]
        if row["id"] != execution["id"]
    ]
    commands = []
    for native_command, event in (
        ("CMD_RUN", "native-owner-run-started"),
        ("CMD_PAUSE", "native-owner-paused"),
    ):
        commands.append(
            controller("execution.command", dict(proof, command=native_command))[
                "command_id"
            ]
        )
        await_event([name], event, seconds=20)
    (control / "owner-resume").write_text(
        "fixture barrier open; await fresh owner RUN\n"
    )
    # A running fixture would finish immediately after its barrier opens. The
    # main native PAUSE must keep its second assignment absent for five seconds.
    time.sleep(5)
    command(
        "docker",
        "exec",
        name,
        "python",
        "-I",
        "-c",
        "from pathlib import Path;assert not Path('/workspace/owner-resumed').exists()",
    )
    paused = host_processes(name)
    if {p["host_pid"] for p in before} != {p["host_pid"] for p in paused}:
        raise RuntimeError("Owner PAUSE replaced a native participant")
    commands.append(
        controller("execution.command", dict(proof, command="CMD_RUN"))["command_id"]
    )
    if len(set(commands)) != 3:
        raise RuntimeError("Owner RUN/PAUSE/resume reused an immutable command")
    await_event([name], "native-owner-resume-finished", seconds=20)
    if command("docker", "wait", name, timeout=15) != "0":
        raise RuntimeError("Owner native pause/resume worker failed")
    info = json.loads(command("docker", "inspect", name))[0]
    if (
        info["State"]["Running"]
        or info["State"]["OOMKilled"]
        or info["Image"] != worker_image
        or info["HostConfig"]["Memory"] != 768 * 1024 * 1024
    ):
        raise RuntimeError(
            "Owner native pause/resume termination/resource binding differs"
        )
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        rows = db.execute(
            "SELECT command_id,command,state,owner,epoch,connection_id,connection_generation FROM native_owner_commands ORDER BY sequence"
        ).fetchall()
        expected = [
            (
                identity,
                native_command,
                "EXECUTION_UNPROVEN",
                "alice",
                execution["epoch"],
                connection,
                execution["connection_generation"],
            )
            for identity, native_command in zip(
                commands, ("CMD_RUN", "CMD_PAUSE", "CMD_RUN"), strict=True
            )
        ]
        owner_dispositions = db.execute(
            "SELECT d.command_id,d.disposition FROM native_owner_command_dispositions d "
            "JOIN native_owner_commands c ON d.command_id=c.command_id "
            "WHERE d.execution_id=c.execution_id ORDER BY c.sequence"
        ).fetchall()
        if owner_dispositions != [(value, "HANDLER_RETURNED") for value in commands]:
            raise RuntimeError(
                "Actual native owner RUN/PAUSE/RUN lacks three durable mailbox returns"
            )
        if (
            rows != expected
            or db.execute("SELECT COUNT(*) FROM native_control_attempts").fetchone()[0]
            != 0
            or db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 2
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1
            or db.execute(
                "SELECT owner,epoch,control_state FROM executions WHERE id=?",
                (execution["id"],),
            ).fetchone()
            != ("alice", execution["epoch"], "OWNED")
        ):
            raise RuntimeError(
                "Owner pause/resume changed original authority or released an uncertain hold"
            )
    after = [
        row
        for row in controller("execution.list", {})["executions"]
        if row["id"] != execution["id"]
    ]
    if unrelated != after:
        raise RuntimeError("Owner pause/resume changed an unrelated reserved witness")
    records = events(name)
    if (
        sum(
            row["event"] == "native-mailbox-disposition-received"
            and row.get("disposition") == "HANDLER_RETURNED"
            for row in records
        )
        != 3
    ):
        raise RuntimeError("Native owner RUN/PAUSE/RUN callback count differs")
    if (
        sum(row["event"] == "native-owner-resume-finished" for row in records) != 1
        or sum(row["event"] == "native-before-consume-admitted" for row in records) != 3
        or any(row["event"] == "native-driver-denied" for row in records)
        or sum(
            row["event"] == "native-startup-run-retired" and row.get("status") == 403
            for row in records
        )
        != 1
    ):
        raise RuntimeError(
            "Owner pause/resume lacks three original native consumption callbacks"
        )
    report["native_owner_pause_resume"] = dict(
        passed=True,
        context_id="D",
        actual_native_executor=True,
        commands=["CMD_RUN", "CMD_PAUSE", "CMD_RUN"],
        fresh_owner_grants=3,
        native_owner_mailbox_returns_durable=3,
        native_owner_mailbox_returns_observed=3,
        startup_run_grants_used=0,
        unused_startup_run_denied=True,
        first_assignment_proven=True,
        continuation_open_while_paused_seconds=5,
        second_assignment_held_until_fresh_run=True,
        same_original_owner_connection_epoch=True,
        replacement_native_processes=False,
        unrelated_witness_unchanged=True,
        holds_retained_after_termination=2,
        spent_workers_retained=1,
        quiescence_proven=False,
        effective_transfer=False,
        runtime_enabled=False,
        full_v08_qualified=False,
    )


def qualify_consumption_fence(
    *,
    temporary,
    prefix,
    context_image,
    config,
    sources,
    worker_image,
    code,
    snapshot,
    ca,
    peers,
    primary_controller,
    control,
    primary_state,
    names,
    networks,
    report,
    command,
    await_event,
    host_processes,
    events,
    owner_commands=False,
    owner_resume=False,
    terminal_case=None,
    terminal_evidence=None,
    live_handoff=False,
    driver_network=None,
    desktop_stack=None,
):
    # A fresh Context keeps the primary ten-slot single-use bound intact.
    # Its second, unstarted witness tests that close fences only one execution.
    original_primary = primary_controller("execution.list", {})
    if owner_commands and owner_resume:
        raise ValueError("Native owner qualification profiles must be separate")
    label = "resume" if owner_resume else "owner" if owner_commands else "consume"
    context_id = "D" if owner_resume else "C" if owner_commands else "B"
    source_id = (
        "owner-resume"
        if owner_resume
        else "owner-probe"
        if owner_commands
        else "consume-probe"
    )
    worker_id = (
        "worker-resume"
        if owner_resume
        else "worker-owner"
        if owner_commands
        else "worker-probe"
    )
    if terminal_case is not None:
        if terminal_evidence is None:
            raise ValueError(
                "Terminal qualification requires a retained evidence directory"
            )
        label = source_id = "terminal-" + terminal_case
        context_id = "T"
        worker_id = "worker-resume"
    if live_handoff:
        label = source_id = "handoff"
        context_id = "H"
        worker_id = "worker-resume"
        if terminal_evidence is None or driver_network is None:
            raise ValueError(
                "Handoff requires retained evidence and an independent DSS"
            )
    name, network = prefix + "-" + label + "-probe", prefix + "-" + label + "-net"
    context_name = prefix + "-" + label + "-context"
    context_network = prefix + "-" + label + "-control"
    command("docker", "network", "create", context_network)
    networks.append(context_network)
    command("docker", "network", "create", "--internal", network)
    networks.append(network)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    state = temporary / (label + "-probe-authority")
    state.mkdir(mode=0o700)
    secure = temporary / (label + "-probe-context-credentials")
    secure.mkdir(mode=0o755)
    for original, target in (
        (ca, "ca.pem"),
        (peers["context"]["cert"], "context.pem"),
        (peers["context"]["key"], "context.key"),
    ):
        shutil.copy2(original, secure / target)
        (secure / target).chmod(0o444)
    probe_config = dict(
        config,
        context_id=context_id,
        allowed_hosts=[f"localhost:{port}", "context:9443"],
        worker_slots={
            "slot-probe": "incarnation-probe",
            "slot-witness": "incarnation-witness",
        },
        worker_credentials=dict(
            profile="single-host-preflight",
            identities={
                peers[worker_id]["pin"]: dict(
                    slot="slot-probe", incarnation="incarnation-probe"
                ),
                peers["worker-0"]["pin"]: dict(
                    slot="slot-witness", incarnation="incarnation-witness"
                ),
            },
        ),
        approved_sources={
            source_id: config["approved_sources"][source_id],
            "witness": config["approved_sources"]["procedure-9"],
        },
    )
    # These separate native authorization probes issue no driver TC/TM calls.
    # They use the core Context CLI, not the DSS driver-factory entrypoint.
    # Never inherit its private driver configuration or simulator catalog binding.
    if not live_handoff:
        probe_config = isolate_audit_probe(probe_config)
    if owner_commands or owner_resume:
        probe_config["native_commands"] = "owner-queue"
    if terminal_case is not None or live_handoff:
        probe_config["native_commands"] = "owner-terminal-candidate"
        probe_config["native_prompts"] = "owner-reply-candidate"
        probe_config["host_settlement"] = dict(
            profile="single-host-terminal-candidate",
            fingerprint=peers["settlement-host"]["pin"],
        )
        if terminal_case is not None:
            probe_config["approved_sources"]["terminal-child"] = dict(
                config["approved_sources"]["terminal-child"],
                driver_binding="context-audit",
            )
    if live_handoff:
        probe_config["native_pause"] = "host-freeze-candidate"
        probe_config["subjects"] = dict(
            probe_config["subjects"], observer=["context:read", "execution:read"]
        )
        probe_config["approved_sources"].pop("terminal-child", None)
        probe_config["approved_sources"]["handoff-child"] = config["approved_sources"][
            "handoff-child"
        ]
    if desktop_stack is not None:
        probe_config["subjects"]["observer"] = ["context:read", "execution:read"]
        for subject in ("alice", "bob"):
            probe_config["subjects"][subject] = sorted(
                set(probe_config["subjects"][subject]) | {"context:read"}
            )
    (secure / "config.json").write_bytes(canonical(probe_config))
    args = [
        "docker",
        "create",
        "--name",
        context_name,
        "--init",
        "--read-only",
        "--network",
        context_network,
        "--publish",
        f"127.0.0.1:{port}:9443",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "512m",
        "--cpu-shares",
        "2048",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
    ]
    for source, destination, mode in (
        (code, "/v08", ",readonly"),
        (sources, "/catalog", ",readonly"),
        (secure, "/credentials", ",readonly"),
        (state, "/state", ""),
    ):
        args += ["--mount", f"type=bind,src={source},dst={destination}{mode}"]
    args += [
        "--env",
        "PYTHONPATH=/v08/server/src:/v08/driver_plugin/src:/v08/src"
        if live_handoff
        else "PYTHONPATH=/v08/server/src",
        "--entrypoint",
        "python",
        context_image,
        "-m",
        "openbexi_spell_dss.context_server"
        if live_handoff
        else "openbexi_spell_server",
        "context",
        "--config",
        "/credentials/config.json",
    ]
    names.append(context_name)
    command(*args)
    command("docker", "network", "connect", "--alias", "context", network, context_name)
    if live_handoff:
        command("docker", "network", "connect", driver_network, context_name)
    command("docker", "start", context_name)
    route = Route(
        f"https://localhost:{port}",
        peers["context"]["pin"],
        tls_context(ca, peers["listener"]["cert"], peers["listener"]["key"]),
    )

    def controller(method, payload, subject="alice"):
        return route.call(
            envelope(
                context_id,
                subject,
                method,
                payload,
                None
                if method in {"execution.list", "source.catalog"}
                else str(uuid.uuid4()),
            )
        )

    from v08_controller_heartbeat import HeartbeatController

    controller = HeartbeatController(controller)
    until = time.monotonic() + 20
    while True:
        try:
            controller("execution.list", {})
            break
        except Exception:
            if time.monotonic() >= until:
                raise RuntimeError("Isolated consumption-probe Context startup failed")
            time.sleep(0.1)
    if desktop_stack is not None:
        from v08_ide_cohort import installed_desktop

        private_controller = controller
        desktop_controller = desktop_stack.enter_context(
            installed_desktop(
                directory=temporary,
                code=code,
                ca=ca,
                peers=peers,
                context_id=context_id,
                context_url=f"https://localhost:{port}",
                report=report,
            )
        )

        def controller(method, payload, subject="alice"):
            # Worker provisioning remains the separately authenticated host path.
            if method == "execution.start":
                return private_controller(method, payload, subject)
            return desktop_controller(method, payload, subject)

        controller.lose = desktop_controller.lose

    entries = {
        entry["procedure_id"]: entry
        for entry in controller("source.catalog", {})["procedures"]
    }
    connection = controller("session.open", {})["connection_id"]
    approved = entries[source_id]
    execution = controller(
        "execution.reserve",
        dict(
            procedure_id=source_id,
            connection_id=connection,
            **{
                key: approved[key]
                for key in (
                    "source_revision",
                    "source_sha256",
                    "runtime_image",
                    "driver_binding",
                )
            },
        ),
    )
    witness_connection = controller("session.open", {})["connection_id"]
    witness = entries["witness"]
    controller(
        "execution.reserve",
        dict(
            procedure_id="witness",
            connection_id=witness_connection,
            **{
                key: witness[key]
                for key in (
                    "source_revision",
                    "source_sha256",
                    "runtime_image",
                    "driver_binding",
                )
            },
        ),
    )
    peer = peers[worker_id]
    params = dict(
        ca=str(ca),
        certificate=str(peer["cert"]),
        key=str(peer["key"]),
        context_url=f"https://localhost:{port}",
        context_fingerprint=peers["context"]["pin"],
        context_id=context_id,
        execution_id=execution["id"],
        worker_slot="slot-probe",
        worker_incarnation="incarnation-probe",
        snapshot_directory=str(snapshot),
    )
    preflight(params)
    grant = controller(
        "execution.start",
        dict(
            execution_id=execution["id"],
            connection_id=connection,
            expected_epoch=execution["epoch"],
            connection_generation=execution["connection_generation"],
            capability=execution["capability"],
        ),
    )["grant"]
    private = temporary / (label + "-probe-credentials")
    private.mkdir(mode=0o755)
    for original, target in (
        (ca, "ca.pem"),
        (peer["cert"], "worker.pem"),
        (peer["key"], "worker.key"),
    ):
        shutil.copy2(original, private / target)
        (private / target).chmod(0o444)
    inside = dict(
        params,
        ca="/credentials/ca.pem",
        certificate="/credentials/worker.pem",
        key="/credentials/worker.key",
        context_url="https://context:9443",
        snapshot_directory="/source",
    )
    (private / "config.json").write_bytes(
        canonical(
            dict(
                preflight=inside,
                grant=grant,
                start_barrier="/control/start",
                native_child_gate=True,
                **(
                    {"native_handoff_probe": True, "native_prompt_gate": True}
                    if live_handoff
                    else {
                        "native_terminal_case": terminal_case,
                        "native_prompt_gate": True,
                    }
                    if terminal_case is not None
                    else {"native_owner_resume_probe": True}
                    if owner_resume
                    else {"native_owner_commands_probe": True}
                    if owner_commands
                    else {"native_consume_fence_probe": True}
                ),
            )
        )
    )
    (private / "config.json").chmod(0o444)
    if live_handoff:
        (control / "handoff-epoch").write_text(grant["request_id"])
    args = [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--init",
        "--read-only",
        "--network",
        network,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        # Two live Executors now remain active through a full 30-second lease
        # timeout. Match the primary two-Executor profile; retain cgroup peaks.
        "1024m" if live_handoff else "768m",
        "--cpus",
        "2",
        "--cpu-shares",
        "128",
        "--user",
        "10003:10003",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
        "--tmpfs",
        "/workspace:rw,nosuid,nodev,size=16m,mode=0700,uid=10003,gid=10003",
    ]
    if live_handoff:
        args += ["--env", "OPENBEXI_V08_RESOURCE_DIAGNOSTICS=1"]
    for source, destination in (
        (snapshot, "/source"),
        (code, "/v08"),
        (private, "/credentials"),
        (control, "/control"),
    ):
        args += ["--mount", f"type=bind,src={source},dst={destination},readonly"]
    args += [
        "--entrypoint",
        "python",
        worker_image,
        "-I",
        "/v08/agent.py",
        "--config",
        "/credentials/config.json",
    ]
    names.append(name)
    host_call = None
    if terminal_case is not None or live_handoff:
        # Host credentials never enter the worker's mounts or process namespace.
        from openbexi_spell_server.settlement import TerminalSettlement

        host_route = Route(
            f"https://localhost:{port}",
            peers["context"]["pin"],
            tls_context(
                ca, peers["settlement-host"]["cert"], peers["settlement-host"]["key"]
            ),
        )

        def host_call(action, **payload):
            return host_route.call(
                dict(
                    schema=TerminalSettlement.SCHEMA,
                    context_id=context_id,
                    execution_id=execution["id"],
                    authority_incarnation=grant["authority_incarnation"],
                    **payload,
                ),
                path="/v1/host/terminal/" + action,
                schema=TerminalSettlement.SCHEMA,
            )

        args[1] = "create"
        args.remove("-d")
        command(*args)
        created = json.loads(command("docker", "inspect", name))[0]
        if created["State"]["Status"] != "created" or created["Image"] != worker_image:
            raise RuntimeError("Host terminal container was not bound before launch")
        host_call("bind", container_id=created["Id"], image=created["Image"])
        command("docker", "start", name)
    else:
        command(*args)
    if live_handoff:
        from openbexi_spell_server.handoff import LiveFamilyHandoff
        from v08_handoff_cohort import qualify_handoff_case
        from v08_terminal_cohort import retire_terminal_probe

        def handoff_call(action, **payload):
            return host_route.call(
                dict(
                    schema=LiveFamilyHandoff.SCHEMA,
                    context_id=context_id,
                    execution_id=execution["id"],
                    authority_incarnation=grant["authority_incarnation"],
                    **payload,
                ),
                path="/v1/host/handoff/" + action,
                schema=LiveFamilyHandoff.SCHEMA,
            )

        from v08_resource_probe import observe

        with observe(command, name, terminal_evidence):
            qualify_handoff_case(
                name=name,
                execution=execution,
                connection=connection,
                controller=controller,
                state=state,
                worker_image=worker_image,
                command=command,
                control=control,
                await_event=await_event,
                report=report,
                host_call=host_call,
                handoff_call=handoff_call,
                output=terminal_evidence,
                verify_step=desktop_stack is not None,
            )
        if primary_controller("execution.list", {}) != original_primary:
            raise RuntimeError("Live handoff changed unrelated primary executions")
        retire_terminal_probe(
            command,
            terminal_evidence,
            name,
            context_name,
            (network, context_network),
            names,
            networks,
        )
        return
    if terminal_case is not None:
        from v08_terminal_cohort import qualify_terminal_case, retire_terminal_probe

        qualify_terminal_case(
            case=terminal_case,
            name=name,
            execution=execution,
            connection=connection,
            controller=controller,
            state=state,
            worker_image=worker_image,
            command=command,
            control=control,
            await_event=await_event,
            events=events,
            report=report,
            host_call=host_call,
        )
        if primary_controller("execution.list", {}) != original_primary:
            raise RuntimeError("Terminal cleanup changed unrelated executions")
        retire_terminal_probe(
            command,
            terminal_evidence,
            name,
            context_name,
            (network, context_network),
            names,
            networks,
        )
        return
    if owner_resume:
        qualify_owner_resume(
            name=name,
            execution=execution,
            connection=connection,
            controller=controller,
            control=control,
            state=state,
            worker_image=worker_image,
            command=command,
            await_event=await_event,
            host_processes=host_processes,
            events=events,
            report=report,
        )
        if primary_controller("execution.list", {}) != original_primary:
            raise RuntimeError("Owner pause/resume changed primary Context executions")
        return
    if owner_commands:
        await_event([name], "native-owner-ready", seconds=45)
        proof = dict(
            execution_id=execution["id"],
            connection_id=connection,
            expected_epoch=execution["epoch"],
            connection_generation=execution["connection_generation"],
            capability=execution["capability"],
            target_admission_id=None,
            command="CMD_STEP",
        )
        first_command = controller("execution.command", proof)["command_id"]
        await_event([name], "native-owner-first-step", seconds=20)
        second_command = controller("execution.command", proof)["command_id"]
        if first_command == second_command:
            raise RuntimeError("Fresh owner STEP commands share an identity")
    await_event(
        [name],
        "native-owner-awaiting-fence"
        if owner_commands
        else "native-consumption-awaiting-fence",
        seconds=45,
    )
    before = host_processes(name)
    # Deliberately exceed the ordinary four-second native socket deadline. The
    # C++ hold is before channel creation; a network timeout cannot pass this probe.
    time.sleep(5)
    # Closing this independent connection must fence only the fresh probe.
    unrelated = {
        row["id"]: row
        for row in controller("execution.list", {})["executions"]
        if row["id"] != execution["id"]
    }
    if (
        controller("session.close", dict(connection_id=connection))["closed"]
        is not True
    ):
        raise RuntimeError("Native consumption probe controller did not close")
    current = {
        row["id"]: row
        for row in controller("execution.list", {})["executions"]
        if row["id"] != execution["id"]
    }
    if unrelated != current:
        raise RuntimeError("Native consumption probe fenced another execution")
    (control / ("owner-continue" if owner_commands else "consume-continue")).write_text(
        "continue into live check after durable close\n"
    )
    await_event(
        [name],
        "native-stale-owner-step-held" if owner_commands else "native-stale-run-held",
        seconds=15,
    )
    marker = (
        "from pathlib import Path;assert Path('/workspace/owner-held').is_file()"
        if owner_commands
        else "from pathlib import Path;assert not Path('/workspace/consume-probe-ran').exists()"
    )
    for _ in range(3):
        command("docker", "exec", name, "python", "-I", "-c", marker)
        time.sleep(0.1)
    after = host_processes(name)
    if {p["host_pid"] for p in before} != {p["host_pid"] for p in after} or len(
        before
    ) != 3:
        raise RuntimeError(
            "Native stale-RUN probe replaced or lost a native participant"
        )
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        row = db.execute(
            "SELECT owner,epoch,control_state FROM executions WHERE id=?",
            (execution["id"],),
        ).fetchone()
        if row != ("alice", execution["epoch"], "CONTROLLER_DISCONNECTED"):
            raise RuntimeError(
                "Native stale-RUN probe changed ownership instead of fencing"
            )
        if owner_commands:
            commands = db.execute(
                "SELECT command_id,command,state,owner,epoch,connection_id,connection_generation FROM native_owner_commands ORDER BY sequence"
            ).fetchall()
            expected = [
                (
                    identity,
                    "CMD_STEP",
                    phase,
                    "alice",
                    execution["epoch"],
                    connection,
                    execution["connection_generation"],
                )
                for identity, phase in (
                    (first_command, "EXECUTION_UNPROVEN"),
                    (second_command, "FORWARD_UNPROVEN"),
                )
            ]
            if (
                commands != expected
                or db.execute(
                    "SELECT COUNT(*) FROM native_control_attempts"
                ).fetchone()[0]
                != 0
            ):
                raise RuntimeError(
                    "Owner STEP lost its fresh identity or bypassed final consumption"
                )
        else:
            attempts = db.execute(
                "SELECT a.state,f.state,c.state FROM native_control_attempts a "
                "JOIN native_control_forwards f ON a.request_id=f.request_id "
                "LEFT JOIN native_control_consumptions c ON a.request_id=c.request_id "
                "WHERE a.execution_id=? AND a.origin_hash=f.origin_hash AND a.operation_digest=f.operation_digest",
                (execution["id"],),
            ).fetchall()
            if attempts != [("DISPATCH_UNCERTAIN", "FORWARD_UNPROVEN", None)]:
                raise RuntimeError(
                    "Stale native RUN obtained a consumption receipt or lost identity"
                )
        if db.execute(
            "SELECT state,COUNT(*) FROM native_members GROUP BY state"
        ).fetchall() != [("REGISTERED_UNPROVEN", 1)]:
            raise RuntimeError("Stale native RUN lost its durable original member")
        if (
            db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 2
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1
        ):
            raise RuntimeError("Native stale-RUN probe reclaimed a hold or worker")
    records = events(name)
    if (
        sum(
            event["event"]
            == (
                "native-owner-authority-denied"
                if owner_commands
                else "native-consumption-authority-denied"
            )
            and event.get("status") == 403
            for event in records
        )
        != 1
    ):
        raise RuntimeError("Native final admission lacks exact live authority denial")
    if (
        owner_commands
        and sum(
            event["event"] == "native-startup-run-retired"
            and event.get("status") == 403
            for event in records
        )
        != 1
    ):
        raise RuntimeError("Owner STEP did not retire its unused startup RUN")
    if (
        owner_commands
        and sum(
            event["event"] == "native-disabled-mutations-held"
            and event.get("operations") == 19
            and event.get("script_marker_absent") is True
            and event.get("variables_unchanged") is True
            for event in records
        )
        != 1
    ):
        raise RuntimeError(
            "Native mutation boundary lacks its original-Executor negative oracle"
        )
    if (
        owner_commands
        and sum(
            event["event"] == "native-context-mutations-held"
            and event.get("operations") == 18
            and event.get("roster_messages") == 8
            and event.get("original_context_denials") is True
            and event.get("variables_unchanged") is True
            and event.get("native_status") == "PAUSED"
            for event in records
        )
        != 1
    ):
        raise RuntimeError("Native Context management/roster oracle is incomplete")
    if any(
        event["event"]
        in (
            {"native-running", "native-finished"}
            if owner_commands
            else {"native-running", "native-finished", "native-before-consume-admitted"}
        )
        for event in records
    ):
        raise RuntimeError("Native stale RUN advanced or was granted consumption")
    # Independent host teardown follows the completed stale-controller oracle.
    # No native close/resume operation is authorized by the fenced connection.
    command("docker", "stop", "--time", "2", name)
    if command("docker", "wait", name, timeout=15) not in {"0", "137", "143"}:
        raise RuntimeError("Native stale-RUN probe host teardown differs")
    info = json.loads(command("docker", "inspect", name))[0]
    if (
        info["State"]["Running"]
        or info["State"]["OOMKilled"]
        or info["Image"] != worker_image
        or info["HostConfig"]["CpuShares"] != 128
    ):
        raise RuntimeError("Native stale-RUN probe termination/image differs")
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        if (
            db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 2
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 1
        ):
            raise RuntimeError(
                "Native stale-RUN teardown released a hold or spent slot"
            )
    if primary_controller("execution.list", {}) != original_primary:
        raise RuntimeError("Consumption probe changed primary Context executions")
    with closing(
        sqlite3.connect(
            "file:" + str(primary_state / "context.sqlite3") + "?mode=ro", uri=True
        )
    ) as db:
        if (
            db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 21
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 10
        ):
            raise RuntimeError(
                "Consumption probe changed primary Context holds/workers"
            )
    report[
        "native_owner_command_fence" if owner_commands else "native_consumption_fence"
    ] = dict(
        passed=True,
        isolated_context_id=context_id,
        primary_ten_slot_pool_preserved=True,
        unrelated_reserved_witness_unchanged=True,
        pre_channel_hold_seconds=5,
        probe_context_holds_retained=2,
        probe_context_workers_spent=1,
        actual_native_executor=True,
        final_authority_status=403,
        forwarded_before_disconnect=True,
        consumption_denied_after_disconnect=True,
        original_three_pids_retained=True,
        **(
            dict(
                first_step_assignment_proven=True,
                second_step_assignment_absent=True,
                fresh_owner_grants=2,
                startup_run_grants_used=0,
                unused_startup_run_denied=True,
                disabled_native_mutations_denied=19,
                disabled_native_context_requests_denied=18,
                disabled_native_roster_messages_denied=8,
                direct_request_denial_before_evaluation=True,
            )
            if owner_commands
            else dict(body_marker_absent=True)
        ),
        original_owner_epoch_retained=True,
        unrelated_executions_unchanged=True,
        control_state="CONTROLLER_DISCONNECTED",
        consumption_receipts=1 if owner_commands else 0,
        durable_members_retained=1,
        member_host_attested=False,
        host_teardown_only=True,
        reservation_retained_after_termination=True,
        worker_spent=True,
        quiescence_proven=False,
        effective_transfer=False,
        runtime_enabled=False,
    )
