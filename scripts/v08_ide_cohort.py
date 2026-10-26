"""Installed A/B/C clients through separate unprivileged Listener/edge processes."""

from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

from openbexi_spell_server.contracts import Fault


@contextmanager
def installed_desktop(*, directory, code, ca, peers, context_id, context_url, report):
    from openbexi_runtime import spell_server_client as ide

    pair = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/v0.8/IDE_PAIR.json").read_text()
    )
    client_hash = hashlib.sha256(Path(ide.__file__).read_bytes()).hexdigest()
    if (
        client_hash
        != pair["ide_source_sha256"]["src/openbexi_runtime/spell_server_client.py"]
        or importlib.metadata.version("openbexi-ide") != pair["ide_version"]
    ):
        raise RuntimeError(
            "Installed native control client differs from the pinned IDE"
        )
    private = directory / ("ide-control-services-" + uuid.uuid4().hex)
    private.mkdir(mode=0o700)
    processes = []
    logs = []
    calls = []

    def port():
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            return reservation.getsockname()[1]

    listener_port, edge_port = port(), port()
    roles = ("alice", "bob", "observer")
    common = dict(ca=str(ca), bind="127.0.0.1", max_handlers=16)
    listener = dict(
        common,
        certificate=str(peers["listener"]["cert"]),
        key=str(peers["listener"]["key"]),
        port=listener_port,
        allowed_hosts=[f"localhost:{listener_port}"],
        edge_fingerprint=peers["edge"]["pin"],
        identities={peers[r]["pin"]: r for r in roles},
        scopes={r: [context_id] for r in roles},
        contexts={
            context_id: dict(url=context_url, fingerprint=peers["context"]["pin"])
        },
        native_command_contexts=[context_id],
    )
    edge = dict(
        common,
        certificate=str(peers["edge"]["cert"]),
        key=str(peers["edge"]["key"]),
        port=edge_port,
        allowed_hosts=[f"localhost:{edge_port}"],
        listener_url=f"https://localhost:{listener_port}",
        listener_fingerprint=peers["listener"]["pin"],
        clients=[peers[r]["pin"] for r in roles],
    )
    try:
        for role, config in (("listener", listener), ("gateway", edge)):
            path = private / (role + ".json")
            path.write_text(json.dumps(config))
            path.chmod(0o600)
            log = (private / (role + ".log")).open("wb")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "openbexi_spell_server",
                        role,
                        "--config",
                        str(path),
                    ],
                    cwd=private,
                    env=dict(os.environ, PYTHONPATH=str(code / "server/src")),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            )
        clients = {
            r: ide.SpellServerClient(
                url=f"https://localhost:{edge_port}",
                fingerprint=peers["edge"]["pin"],
                ca=ca,
                certificate=peers[r]["cert"],
                key=peers[r]["key"],
            )
            for r in roles
        }
        until = time.monotonic() + 15
        while True:
            try:
                if clients["observer"].contexts() != [context_id]:
                    raise RuntimeError("IDE Context scope differs")
                break
            except ide.SpellServerError:
                if (
                    any(p.poll() is not None for p in processes)
                    or time.monotonic() >= until
                ):
                    raise RuntimeError(
                        "IDE Listener/gateway did not become ready"
                    ) from None
                time.sleep(0.05)
        if clients["observer"].read(context_id, "health")["native_commands"]:
            raise RuntimeError("Observer was advertised native mutation authority")
        expected = {"CMD_RUN", "CMD_STEP", "CMD_PAUSE", "CMD_ABORT", "CMD_CLOSE"}
        if (
            set(clients["alice"].read(context_id, "health")["native_commands"])
            != expected
        ):
            raise RuntimeError("Configured native control capability is missing")

        def controller(method, payload, subject="alice"):
            client = clients[subject]
            key = str(uuid.uuid4())
            try:
                if method in {"execution.list", "source.catalog"}:
                    result = client.read(
                        context_id,
                        "executions" if method == "execution.list" else "procedures",
                    )
                elif method == "execution.command":
                    eid = payload["execution_id"]
                    cached = client._controllers.get((context_id, eid))
                    if cached is not None and payload == dict(
                        cached,
                        command=payload["command"],
                        target_admission_id=payload["target_admission_id"],
                    ):
                        result = client.command(
                            context_id,
                            eid,
                            payload["command"],
                            key=key,
                            target_admission_id=payload["target_admission_id"],
                        )
                    else:
                        # Hostile callers bypass their UI/proof checks, including
                        # stale or malformed owner proofs in terminal negatives.
                        result = client.request(
                            "POST",
                            f"/v1/contexts/{context_id}/commands",
                            payload,
                            key=key,
                        )["result"]
                else:
                    result = client.authority(context_id, method, payload, key=key)
                    if method in {"execution.reserve", "execution.rebind"}:
                        client.remember_controller(context_id, result)
                calls.append(
                    dict(
                        subject=subject,
                        method=method,
                        command=payload.get("command"),
                        status=200,
                    )
                )
                return result
            except ide.SpellServerError as error:
                calls.append(
                    dict(
                        subject=subject,
                        method=method,
                        command=payload.get("command"),
                        status=error.status,
                    )
                )
                raise Fault(error.status, "ide_request_denied") from error

        receipt = dict(
            context_id=context_id,
            installed_client_sha256=client_hash,
            ide_commit=pair["ide_commit"],
            ide_version=pair["ide_version"],
            listener_pid=processes[0].pid,
            gateway_pid=processes[1].pid,
            three_certificate_identities=True,
            public_launch_enabled=False,
            browser_tested=False,
            calls=calls,
        )
        report["native_ide"] = receipt
        report.setdefault("native_ide_profiles", []).append(receipt)
        yield controller
        receipt["passed"] = True
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in logs:
            log.close()
