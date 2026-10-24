"""Independent host verification of Listener loss while native workers advance.

Only the trusted host operates Docker. Neither service nor worker receives a
Docker socket, host manager, recovery authority or a replacement execution grant.
"""

from contextlib import closing
import hashlib
import http.client
import json
import os
import shutil
import socket
import sqlite3
import time

from openbexi_spell_server.contracts import canonical, decode
from openbexi_spell_server.transport import tls_context


def qualify_listener_survival(
    *,
    directory,
    code,
    ca,
    peers,
    context_name,
    context_image,
    control_network,
    state,
    worker_names,
    names,
    report,
    command,
    host_processes,
):
    credentials = directory / "listener-credentials"
    credentials.mkdir(mode=0o755)
    for original, target in (
        (ca, "ca.pem"),
        (peers["listener"]["cert"], "listener.pem"),
        (peers["listener"]["key"], "listener.key"),
    ):
        shutil.copy2(original, credentials / target)
        (credentials / target).chmod(0o444)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    client_pin = hashlib.sha256(b"native-listener-read-only-observer").hexdigest()
    config = dict(
        ca="/credentials/ca.pem",
        certificate="/credentials/listener.pem",
        key="/credentials/listener.key",
        bind="0.0.0.0",
        port=9444,
        allowed_hosts=[f"localhost:{port}"],
        max_handlers=16,
        edge_fingerprint=peers["edge"]["pin"],
        identities={client_pin: "observer"},
        scopes={"observer": ["A"]},
        contexts={
            "A": dict(url="https://context:9443", fingerprint=peers["context"]["pin"])
        },
    )
    (credentials / "config.json").write_bytes(canonical(config))
    (credentials / "config.json").chmod(0o444)
    listener_name = context_name + "-listener"
    arguments = [
        "docker",
        "run",
        "-d",
        "--name",
        listener_name,
        "--init",
        "--read-only",
        "--network",
        control_network,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--publish",
        f"127.0.0.1:{port}:9444",
        "--mount",
        f"type=bind,src={credentials},dst=/credentials,readonly",
        "--mount",
        f"type=bind,src={code},dst=/v08,readonly",
        "--env",
        "PYTHONPATH=/v08/server/src",
        "--entrypoint",
        "python",
        context_image,
        "-m",
        "openbexi_spell_server",
        "listener",
        "--config",
        "/credentials/config.json",
    ]
    edge_tls = tls_context(ca, peers["edge"]["cert"], peers["edge"]["key"])

    def read(path, *, tls=edge_tls):
        connection = http.client.HTTPSConnection(
            "localhost", port, context=tls, timeout=2
        )
        try:
            connection.connect()
            if (
                hashlib.sha256(
                    connection.sock.getpeercert(binary_form=True)
                ).hexdigest()
                != peers["listener"]["pin"]
            ):
                raise RuntimeError("Listener certificate pin differs")
            connection.request(
                "GET", path, headers={"X-OpenBEXI-Client-Fingerprint": client_pin}
            )
            response = connection.getresponse()
            value = decode(response.read(65537))
            return response.status, value
        finally:
            connection.close()

    def start():
        container = command(*arguments)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                status, value = read("/v1/health")
                if status == 200 and value.get("status") == "ready":
                    break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.05)
        else:
            raise RuntimeError("Independent Listener did not become ready")
        info = json.loads(command("docker", "inspect", listener_name))[0]
        if info["HostConfig"]["Privileged"] or any(
            "docker.sock" in m["Destination"] for m in info["Mounts"]
        ):
            raise RuntimeError("Listener gained a host manager/socket")
        return container, info["State"]["Pid"]

    def progress():
        return [
            int(
                command(
                    "docker",
                    "exec",
                    name,
                    "python",
                    "-I",
                    "-c",
                    "from pathlib import Path;print(Path('/tmp/listener-progress').read_text())",
                )
            )
            for name in worker_names
        ]

    def native_pids():
        return [[p["host_pid"] for p in host_processes(name)] for name in worker_names]

    def snapshot():
        status, value = read("/v1/contexts/A/snapshot")
        if status != 200:
            raise RuntimeError("Listener could not read the live Context")
        status, executions = read("/v1/contexts/A/executions")
        if status != 200:
            raise RuntimeError("Listener could not observe native reservations")
        return value["result"], executions["result"]["executions"]

    names.append(listener_name)
    first, first_pid = start()
    before, executions = snapshot()
    if len(executions) != 10 or any(row["owner"] != "alice" for row in executions):
        raise RuntimeError("Native Listener baseline ownership differs")
    # An assigned worker cert cannot impersonate the separately pinned edge.
    wrong_role = tls_context(ca, peers["worker-0"]["cert"], peers["worker-0"]["key"])
    if read("/v1/contexts/A/executions", tls=wrong_role)[0] != 403:
        raise RuntimeError("Worker certificate gained Listener edge authority")
    pids_before = native_pids()
    context_before = json.loads(command("docker", "inspect", context_name))[0]["State"]
    counts_before = progress()
    command("docker", "kill", "--signal", "KILL", listener_name)
    if command("docker", "wait", listener_name) != "137":
        raise RuntimeError("Listener loss was not an actual process kill")
    counts_during = progress()
    if any(
        after <= before
        for before, after in zip(counts_before, counts_during, strict=True)
    ):
        raise RuntimeError("A native procedure did not advance during Listener loss")
    if native_pids() != pids_before:
        raise RuntimeError("Native process changed during Listener loss")
    # Recreate from the same fixed config; no Context or worker is replaced.
    command("docker", "rm", listener_name)
    second, second_pid = start()
    after, retained = snapshot()
    context_after = json.loads(command("docker", "inspect", context_name))[0]["State"]
    if (
        first == second
        or first_pid == second_pid
        or before["incarnation"] != after["incarnation"]
        or executions != retained
        or native_pids() != pids_before
        or context_before["Pid"] != context_after["Pid"]
        or context_before["StartedAt"] != context_after["StartedAt"]
    ):
        raise RuntimeError(
            "Listener replacement changed native/Context identity or ownership"
        )
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as audit:
        if (
            audit.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 10
            or audit.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 10
        ):
            raise RuntimeError(
                "Listener loss changed held reservations or spent workers"
            )
    report["native_listener_survival"] = dict(
        component_tested=True,
        listener_killed=True,
        replacement_process_verified=True,
        native_procedures_advancing=10,
        native_pid_count=30,
        native_pids_unchanged=True,
        context_process_unchanged=True,
        context_incarnation_unchanged=True,
        owners_epochs_generations_unchanged=True,
        held_reservations=10,
        spent_workers=10,
        worker_as_edge_denied=True,
        listener_has_no_host_manager=True,
        observer_only=True,
        controller_disconnect_qualified=False,
        native_recovery_qualified=False,
        full_v08_qualified=False,
        progress_before=counts_before,
        progress_during_outage=counts_during,
    )
