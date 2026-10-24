"""Host-owned stale RUN probe against the actual candidate native Executor.

The fresh worker has its own slot, certificate, connection, execution and network.
No authority/container introspection is delegated to the Context or worker.
"""

from contextlib import closing
import json
import shutil
import sqlite3
import time

from openbexi_spell_server.contracts import canonical
from openbexi_spell_server.worker import preflight


def qualify_consumption_fence(
    *,
    temporary,
    prefix,
    context_name,
    worker_image,
    code,
    snapshot,
    ca,
    peers,
    port,
    entries,
    controller,
    control,
    state,
    names,
    networks,
    report,
    command,
    await_event,
    host_processes,
    events,
):
    name, network = prefix + "-consume-probe", prefix + "-consume-net"
    command("docker", "network", "create", "--internal", network)
    networks.append(network)
    command("docker", "network", "connect", "--alias", "context", network, context_name)
    connection = controller("session.open", {})["connection_id"]
    approved = entries["consume-probe"]
    execution = controller(
        "execution.reserve",
        dict(
            procedure_id="consume-probe",
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
    peer = peers["worker-probe"]
    params = dict(
        ca=str(ca),
        certificate=str(peer["cert"]),
        key=str(peer["key"]),
        context_url=f"https://localhost:{port}",
        context_fingerprint=peers["context"]["pin"],
        context_id="A",
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
    private = temporary / "consume-probe-credentials"
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
                native_consume_fence_probe=True,
            )
        )
    )
    (private / "config.json").chmod(0o444)
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
        "768m",
        "--cpus",
        "2",
        "--user",
        "10003:10003",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
        "--tmpfs",
        "/workspace:rw,nosuid,nodev,size=16m",
    ]
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
    command(*args)
    await_event([name], "native-consumption-awaiting-fence", seconds=45)
    before = host_processes(name)
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
    (control / "consume-continue").write_text(
        "continue into live check after durable close\n"
    )
    await_event([name], "native-stale-run-held", seconds=15)
    marker = "from pathlib import Path;assert not Path('/workspace/consume-probe-ran').exists()"
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
        if (
            db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 22
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 11
        ):
            raise RuntimeError("Native stale-RUN probe reclaimed a hold or worker")
    records = events(name)
    if (
        sum(
            event["event"] == "native-consumption-authority-denied"
            and event.get("status") == 403
            for event in records
        )
        != 1
    ):
        raise RuntimeError("Native final admission lacks exact live authority denial")
    if any(
        event["event"]
        in {"native-running", "native-finished", "native-before-consume-admitted"}
        for event in records
    ):
        raise RuntimeError("Native stale RUN advanced or was granted consumption")
    (control / "consume-probe-stop").write_text(
        "host completed retained-process observation\n"
    )
    if command("docker", "wait", name, timeout=30) != "0":
        raise RuntimeError("Native stale-RUN probe failed cleanup")
    info = json.loads(command("docker", "inspect", name))[0]
    if (
        info["State"]["Running"]
        or info["State"]["OOMKilled"]
        or info["Image"] != worker_image
    ):
        raise RuntimeError("Native stale-RUN probe termination/image differs")
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        if (
            db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 22
            or db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 11
        ):
            raise RuntimeError(
                "Native stale-RUN teardown released a hold or spent slot"
            )
    report["native_consumption_fence"] = dict(
        passed=True,
        actual_native_executor=True,
        final_authority_status=403,
        forwarded_before_disconnect=True,
        consumption_denied_after_disconnect=True,
        original_three_pids_retained=True,
        body_marker_absent=True,
        original_owner_epoch_retained=True,
        unrelated_executions_unchanged=True,
        control_state="CONTROLLER_DISCONNECTED",
        consumption_receipts=0,
        reservation_retained_after_termination=True,
        worker_spent=True,
        quiescence_proven=False,
        effective_transfer=False,
        runtime_enabled=False,
    )
