"""Actual retained native launch cohort, not full v0.8/release qualification.

The trusted host provisions ten isolated single-use containers. Each agent uses
real mTLS preflight/consumption against Context before opening a native Listener,
Context and Executor. No Docker socket/host manager enters a worker or Context.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server/src"))
from openbexi_spell_server.contracts import canonical, envelope  # noqa: E402
from openbexi_spell_server.transport import Route, tls_context  # noqa: E402
from openbexi_spell_server.worker import preflight  # noqa: E402
from qualify_v08_native_boundary import ARCHIVE, ARCHIVE_SHA256, ARCHIVE_SIZE, IMAGE  # noqa: E402

PERMISSIONS = [
    "execution:read",
    "execution:start",
    "execution:control",
    "execution:request_control",
]


def command(*args, timeout=30):
    result = subprocess.run(list(map(str, args)), capture_output=True, timeout=timeout)
    if result.returncode:
        # Never include arbitrary command stderr/configuration in an exception.
        raise RuntimeError("Host operation failed: " + str(args[0]))
    return (
        (result.stdout + (result.stderr if args[:2] == ("docker", "logs") else b""))
        .decode()
        .strip()
    )


def pki(directory):
    directory.mkdir()
    command(
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=native-test-ca",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout",
        directory / "ca.key",
        "-out",
        directory / "ca.pem",
    )
    extensions = directory / "extensions.cnf"
    extensions.write_text(
        "subjectAltName=DNS:localhost,DNS:context,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth,clientAuth\n"
    )
    peers = {}
    for name in ["context", "listener"] + ["worker-" + str(n) for n in range(10)]:
        key, cert = directory / (name + ".key"), directory / (name + ".pem")
        command(
            "openssl",
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-subj",
            "/CN=" + name,
            "-keyout",
            key,
            "-out",
            directory / (name + ".csr"),
        )
        command(
            "openssl",
            "x509",
            "-req",
            "-in",
            directory / (name + ".csr"),
            "-CA",
            directory / "ca.pem",
            "-CAkey",
            directory / "ca.key",
            "-CAcreateserial",
            "-days",
            "1",
            "-extfile",
            extensions,
            "-out",
            cert,
        )
        peers[name] = dict(
            cert=cert,
            key=key,
            pin=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest(),
        )
    return directory / "ca.pem", peers


def load_runtime(directory, output):
    archive = directory / "runtime.tar.gz"
    sha, size, deadline = hashlib.sha256(), 0, time.monotonic() + 120
    with urlopen(ARCHIVE, timeout=30) as response, archive.open("xb") as stream:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > ARCHIVE_SIZE or time.monotonic() > deadline:
                raise RuntimeError("Runtime archive bound exceeded")
            sha.update(chunk)
            stream.write(chunk)
    if size != ARCHIVE_SIZE or sha.hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("Runtime archive identity differs")
    (output / "docker-load.log").write_text(
        command("docker", "load", "--input", archive, timeout=120) + "\n"
    )
    if command("docker", "image", "inspect", "--format", "{{.Id}}", IMAGE) != IMAGE:
        raise RuntimeError("Runtime image identity differs")


def events(name):
    raw = command("docker", "logs", name, timeout=10)
    result = []
    if len(raw) > 1024 * 1024:
        raise RuntimeError("Worker log capacity exceeded")
    for line in raw.splitlines():
        try:
            value = json.loads(line)
            if type(value) is dict and "event" in value:
                result.append(value)
        except ValueError:
            continue
    return result


def await_event(names, event, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        all_ready = True
        for name in names:
            records = events(name)
            if any(r["event"] == "native-worker-failed" for r in records):
                raise RuntimeError("Native worker failed before " + event)
            if not any(r["event"] == event for r in records):
                state = json.loads(command("docker", "inspect", name))[0]["State"]
                if not state["Running"]:
                    raise RuntimeError("Native worker stopped before " + event)
                all_ready = False
        if all_ready:
            return
        time.sleep(0.1)
    raise TimeoutError("Native cohort did not reach " + event)


def host_processes(name):
    lines = command("docker", "top", name, "-eo", "pid,comm").splitlines()[1:]
    rows = []
    for line in lines:
        pid, executable = line.split(maxsplit=1)
        if executable.startswith("SPELL-"):
            rows.append(dict(host_pid=int(pid), executable=executable))
    if len(rows) != 3 or not any("Executor" in p["executable"] for p in rows):
        raise RuntimeError("Expected distinct real native Listener/Context/Executor")
    return rows


def main():
    output = ROOT / ".qualification/v08-native-launch" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    report = dict(
        passed=False,
        native_launch_path_tested=False,
        native_concurrency_verified=False,
        native_pause_qualified=False,
        external_driver_effects_enabled=False,
        context_audit_events_enabled=True,
        runtime_enabled=False,
        full_v08_qualified=False,
        image=IMAGE,
        archive_sha256=ARCHIVE_SHA256,
        git_head=command("git", "rev-parse", "HEAD"),
        source_sha256={},
        workers=[],
        host_cpu_count=os.cpu_count(),
        host_memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
    )
    inputs = list((ROOT / "server/src/openbexi_spell_server").glob("*.py")) + [
        ROOT / "host_runtime/python/v08_worker.py",
        Path(__file__),
        ROOT / "scripts/qualify_v08_native_boundary.py",
    ]
    for path in inputs:
        report["source_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    prefix = "spell-v08-launch-" + uuid.uuid4().hex[:12]
    names, networks = [], []
    try:
        with tempfile.TemporaryDirectory(prefix="spell-native-launch-") as temporary:
            temporary = Path(temporary)
            try:
                if os.getuid() == 0:
                    raise RuntimeError(
                        "Qualification must run as a non-root host operator"
                    )
                load_runtime(temporary, output)
                ca, peers = pki(temporary / "pki")
                code = temporary / "code"
                package = code / "server/src/openbexi_spell_server"
                package.mkdir(parents=True)
                for path in (ROOT / "server/src/openbexi_spell_server").glob("*.py"):
                    shutil.copy2(path, package / path.name)
                shutil.copy2(
                    ROOT / "host_runtime/python/v08_worker.py", code / "agent.py"
                )
                # Context needs Git object readers; the frozen worker image has
                # no Git. Record this separate development image, never call it
                # the immutable native worker image or a release build.
                build = temporary / "context-image"
                build.mkdir()
                base = prefix + "-base"
                command("docker", "tag", IMAGE, base)
                (build / "Dockerfile").write_text(
                    "FROM "
                    + base
                    + "\nUSER root\nRUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*\nUSER 10003:10003\n"
                )
                context_image = prefix + "-authority"
                built = subprocess.run(
                    ["docker", "build", "-t", context_image, str(build)],
                    capture_output=True,
                    timeout=180,
                )
                (output / "context-image-build.log").write_bytes(
                    built.stdout + built.stderr
                )
                if built.returncode:
                    raise RuntimeError("Isolated Context image build failed")
                report["context_image"] = command(
                    "docker", "image", "inspect", "--format", "{{.Id}}", context_image
                )
                report["context_git_version"] = command(
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--entrypoint",
                    "git",
                    context_image,
                    "--version",
                )
                sources, snapshot = temporary / "git", temporary / "snapshot"
                sources.mkdir()
                command("git", "init", "-q", sources)
                fixture = "import os,time\ndeadline=time.monotonic()+40\nwhile not os.path.exists('/control/finish'):\n    if time.monotonic()>deadline:raise RuntimeError('finish barrier expired')\n    time.sleep(0.05)\nRESULT={index}*{index}\nassert RESULT == {square}\n"
                for n in range(10):
                    (sources / ("procedure_" + str(n) + ".py")).write_text(
                        fixture.replace("{index}", str(n)).replace(
                            "{square}", str(n * n)
                        )
                    )
                command("git", "-C", sources, "add", ".")
                command(
                    "git",
                    "-C",
                    sources,
                    "-c",
                    "user.name=Qualification",
                    "-c",
                    "user.email=qualification@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-qm",
                    "immutable native cohort",
                )
                revision = command("git", "-C", sources, "rev-parse", "HEAD")
                snapshot.mkdir(mode=0o755)
                for source in sources.glob("*.py"):
                    shutil.copy2(source, snapshot / source.name)
                slots = {"slot-" + str(n): "incarnation-" + str(n) for n in range(10)}
                catalog = {
                    "procedure-" + str(n): dict(
                        repository="/catalog",
                        revision=revision,
                        entrypoint="procedure_" + str(n) + ".py",
                        runtime_image=IMAGE,
                        driver_binding="context-audit",
                        aliases=[],
                    )
                    for n in range(10)
                }
                credentials = dict(
                    profile="single-host-preflight",
                    identities={
                        peers["worker-" + str(n)]["pin"]: dict(
                            slot="slot-" + str(n), incarnation=slots["slot-" + str(n)]
                        )
                        for n in range(10)
                    },
                )
                control_network = prefix + "-control"
                command("docker", "network", "create", control_network)
                networks.append(control_network)
                state = temporary / "authority"
                state.mkdir(mode=0o700)
                secure = temporary / "context-credentials"
                secure.mkdir(mode=0o755)
                for original, target in [
                    (ca, "ca.pem"),
                    (peers["context"]["cert"], "context.pem"),
                    (peers["context"]["key"], "context.key"),
                ]:
                    shutil.copy2(original, secure / target)
                    (secure / target).chmod(0o444)
                with socket.socket() as port_reservation:
                    port_reservation.bind(("127.0.0.1", 0))
                    port = port_reservation.getsockname()[1]
                config = dict(
                    ca="/credentials/ca.pem",
                    certificate="/credentials/context.pem",
                    key="/credentials/context.key",
                    bind="0.0.0.0",
                    port=9443,
                    allowed_hosts=[f"localhost:{port}", "context:9443"],
                    max_handlers=32,
                    context_id="A",
                    state_directory="/state",
                    listener_fingerprint=peers["listener"]["pin"],
                    subjects={"alice": PERMISSIONS, "bob": PERMISSIONS},
                    worker_slots=slots,
                    approved_sources=catalog,
                    worker_credentials=credentials,
                    worker_launch="retained-single-use",
                )
                (secure / "config.json").write_bytes(canonical(config))
                context_name = prefix + "-context"
                args = [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    context_name,
                    "--init",
                    "--read-only",
                    "--network",
                    control_network,
                    "--network-alias",
                    "context",
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
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                ]
                for src, dst, mode in [
                    (code, "/v08", ",readonly"),
                    (sources, "/catalog", ",readonly"),
                    (secure, "/credentials", ",readonly"),
                    (state, "/state", ""),
                ]:
                    args.extend(["--mount", f"type=bind,src={src},dst={dst}{mode}"])
                args.extend(
                    [
                        "--env",
                        "PYTHONPATH=/v08/server/src",
                        "--entrypoint",
                        "python",
                        context_image,
                        "-m",
                        "openbexi_spell_server",
                        "context",
                        "--config",
                        "/credentials/config.json",
                    ]
                )
                names.append(context_name)
                command(*args)
                route = Route(
                    f"https://localhost:{port}",
                    peers["context"]["pin"],
                    tls_context(
                        ca, peers["listener"]["cert"], peers["listener"]["key"]
                    ),
                )

                def controller(method, payload, subject="alice"):
                    return route.call(
                        envelope(
                            "A",
                            subject,
                            method,
                            payload,
                            str(uuid.uuid4())
                            if method not in {"execution.list", "source.catalog"}
                            else None,
                        )
                    )

                deadline = time.monotonic() + 20
                while True:
                    try:
                        route.call(envelope("A", "alice", "execution.list", {}))
                        break
                    except Exception as startup_error:
                        report["context_startup_error"] = dict(
                            type=type(startup_error).__name__,
                            code=str(startup_error)[:160],
                            cause_type=type(startup_error.__cause__).__name__,
                            cause=str(startup_error.__cause__)[:200],
                        )
                        if time.monotonic() >= deadline:
                            report["context_port_mapping"] = command(
                                "docker", "port", context_name
                            )
                            raise RuntimeError("Isolated Context startup failed")
                        time.sleep(0.1)
                procedures = route.call(envelope("A", "alice", "source.catalog", {}))
                # Catalog shape and bindings come from Context's own immutable
                # Git verification, never from an unchecked worker report.
                entries = {
                    entry["procedure_id"]: entry for entry in procedures["procedures"]
                }
                connection = controller("session.open", {})["connection_id"]
                control = temporary / "control"
                control.mkdir(mode=0o755)
                executions, worker_names, containers, launch_commands = [], [], [], []
                for n in range(10):
                    name = prefix + "-" + str(n)
                    network = name + "-net"
                    command(
                        "docker",
                        "network",
                        "create",
                        "--internal",
                        network,
                    )
                    networks.append(network)
                    command(
                        "docker",
                        "network",
                        "connect",
                        "--alias",
                        "context",
                        network,
                        context_name,
                    )
                    approved = entries["procedure-" + str(n)]
                    execution = controller(
                        "execution.reserve",
                        dict(
                            procedure_id="procedure-" + str(n),
                            connection_id=connection,
                            **{
                                k: approved[k]
                                for k in (
                                    "source_revision",
                                    "source_sha256",
                                    "runtime_image",
                                    "driver_binding",
                                )
                            },
                        ),
                    )
                    executions.append(execution)
                    peer = peers["worker-" + str(n)]
                    params = dict(
                        ca=str(ca),
                        certificate=str(peer["cert"]),
                        key=str(peer["key"]),
                        context_url=f"https://localhost:{port}",
                        context_fingerprint=peers["context"]["pin"],
                        context_id="A",
                        execution_id=execution["id"],
                        worker_slot="slot-" + str(n),
                        worker_incarnation=slots["slot-" + str(n)],
                        snapshot_directory=str(snapshot),
                    )
                    preflight(params)
                    admitted = controller(
                        "execution.start",
                        dict(
                            execution_id=execution["id"],
                            connection_id=connection,
                            expected_epoch=execution["epoch"],
                            connection_generation=execution["connection_generation"],
                            capability=execution["capability"],
                        ),
                    )["grant"]
                    private = temporary / ("credentials-" + str(n))
                    private.mkdir(mode=0o755)
                    for original, target in [
                        (ca, "ca.pem"),
                        (peer["cert"], "worker.pem"),
                        (peer["key"], "worker.key"),
                    ]:
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
                                grant=admitted,
                                start_barrier="/control/start",
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
                    for src, dst in [
                        (snapshot, "/source"),
                        (code, "/v08"),
                        (private, "/credentials"),
                        (control, "/control"),
                    ]:
                        args.extend(
                            ["--mount", f"type=bind,src={src},dst={dst},readonly"]
                        )
                    args.extend(
                        [
                            "--entrypoint",
                            "python",
                            IMAGE,
                            "-I",
                            "/v08/agent.py",
                            "--config",
                            "/credentials/config.json",
                        ]
                    )
                    launch_commands.append(list(args))
                    names.append(name)
                    container = command(*args)
                    worker_names.append(name)
                    containers.append(container)
                    await_event([name], "native-ready", seconds=40)
                await_event(worker_names, "native-ready")
                report["paused_cohort"] = [
                    {"container": container, "processes": host_processes(name)}
                    for name, container in zip(worker_names, containers, strict=True)
                ]
                (control / "start").write_text("start once\n")
                await_event(worker_names, "native-running", seconds=30)
                report["running_cohort"] = [
                    {"container": container, "processes": host_processes(name)}
                    for name, container in zip(worker_names, containers, strict=True)
                ]
                all_pids = [
                    p["host_pid"]
                    for item in report["running_cohort"]
                    for p in item["processes"]
                ]
                if len(set(all_pids)) != 30:
                    raise RuntimeError(
                        "Native cohort does not have thirty distinct live PIDs"
                    )
                # The host verifies network boundaries independently of the agent.
                peer_info = json.loads(command("docker", "inspect", worker_names[1]))[0]
                peer_ip = next(iter(peer_info["NetworkSettings"]["Networks"].values()))[
                    "IPAddress"
                ]
                probe = "import socket,sys\ntry:s=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=0.5)\nexcept OSError:sys.exit(0)\nelse:s.close();sys.exit(1)"
                for address, denied_port in [(peer_ip, 9980), ("1.1.1.1", 443)]:
                    command(
                        "docker",
                        "exec",
                        worker_names[0],
                        "python",
                        "-I",
                        "-c",
                        probe,
                        address,
                        denied_port,
                    )
                report["network_denials"] = dict(
                    cross_worker_native_port=True, external_tcp=True
                )
                (control / "finish").write_text("finish fixture\n")
                with ThreadPoolExecutor(max_workers=10) as pool:
                    exits = list(
                        pool.map(
                            lambda name: command("docker", "wait", name, timeout=90),
                            worker_names,
                        )
                    )
                if exits != ["0"] * 10:
                    raise RuntimeError("Native cohort did not exit successfully")
                for name, container, execution in zip(
                    worker_names, containers, executions, strict=True
                ):
                    records = events(name)
                    if not any(r["event"] == "native-finished" for r in records):
                        raise RuntimeError("Native completion evidence absent")
                    info = json.loads(command("docker", "inspect", name))[0]
                    if (
                        info["State"]["Running"]
                        or info["State"]["OOMKilled"]
                        or info["HostConfig"]["Privileged"]
                        or not info["HostConfig"]["ReadonlyRootfs"]
                        or info["Image"] != IMAGE
                    ):
                        raise RuntimeError("Worker isolation/termination differs")
                    report["workers"].append(
                        dict(
                            container=container,
                            execution_id=execution["id"],
                            events=records,
                            whole_container_terminated=True,
                            image=info["Image"],
                            privileged=False,
                            readonly_root=True,
                        )
                    )
                # A physical clone with the same certificate, incarnation and
                # original grant must fail before opening any native session.
                clone = prefix + "-clone"
                clone_command = list(launch_commands[1])
                clone_command[clone_command.index("--name") + 1] = clone
                names.append(clone)
                command(*clone_command)
                if command("docker", "wait", clone, timeout=15) != "1":
                    raise RuntimeError("Cloned spent worker was not rejected")
                clone_events = events(clone)
                if any(
                    item["event"]
                    in {"native-ready", "native-running", "native-finished"}
                    for item in clone_events
                ) or not any(
                    item["event"] == "native-worker-failed"
                    and item.get("error") == "context_request_denied"
                    for item in clone_events
                ):
                    raise RuntimeError(
                        "Cloned worker denial did not precede native launch"
                    )
                report["physical_worker_clone_denied"] = True
                bob = controller("session.open", {}, "bob")["connection_id"]
                first = executions[0]
                claim = controller(
                    "execution.claim",
                    dict(
                        execution_id=first["id"],
                        connection_id=bob,
                        expected_epoch=first["epoch"],
                    ),
                    "bob",
                )
                decision = controller(
                    "execution.decide",
                    dict(
                        execution_id=first["id"],
                        connection_id=connection,
                        expected_epoch=first["epoch"],
                        connection_generation=first["connection_generation"],
                        capability=first["capability"],
                        claim_id=claim["claim_id"],
                        decision="accept",
                    ),
                )
                if decision["state"] != "BLOCKED":
                    raise RuntimeError(
                        "Unproved native quiescence allowed ownership transfer"
                    )
                report["native_handoff"] = dict(
                    state=decision["state"],
                    owner_preserved=True,
                    quiescence_proven=False,
                    phase="after_container_termination",
                )
                retained = controller("execution.list", {})["executions"]
                if len(retained) != 10 or any(
                    row["owner"] != "alice" for row in retained
                ):
                    raise RuntimeError(
                        "Native completion changed ownership/reservation"
                    )
                with closing(
                    sqlite3.connect(
                        "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
                    )
                ) as audit:
                    if (
                        audit.execute("SELECT SUM(spent) FROM workers").fetchone()[0]
                        != 10
                        or audit.execute(
                            "SELECT COUNT(*) FROM reservations"
                        ).fetchone()[0]
                        != 10
                    ):
                        raise RuntimeError(
                            "Native completion released a hold or worker slot"
                        )
                with closing(
                    sqlite3.connect(
                        "file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True
                    )
                ) as audit:
                    event_count = audit.execute(
                        "SELECT COUNT(*) FROM native_driver_events"
                    ).fetchone()[0]
                    bodies = [
                        json.loads(row[0])
                        for row in audit.execute(
                            "SELECT body FROM events WHERE type='NATIVE_DRIVER_EVENT'"
                        )
                    ]
                    for execution in executions:
                        messages = [
                            body["message"]
                            for body in bodies
                            if body["execution_id"] == execution["id"]
                        ]
                        if (
                            sum(
                                message.startswith("Procedure started:")
                                for message in messages
                            )
                            != 1
                            or sum(
                                message.startswith("Procedure finished:")
                                for message in messages
                            )
                            != 1
                        ):
                            raise RuntimeError(
                                "Native lifecycle events lack unique durable receipts"
                            )
                    if event_count < 20:
                        raise RuntimeError(
                            "Native lifecycle events lack durable receipts"
                        )
                report["native_driver_events_persisted"] = event_count
                first_row = next(row for row in retained if row["id"] == first["id"])
                if (
                    first_row["epoch"] != first["epoch"]
                    or first_row["control_state"] != "RECOVERY_REQUIRED"
                    or any(
                        row["control_state"] != "OWNED"
                        for row in retained
                        if row["id"] != first["id"]
                    )
                ):
                    raise RuntimeError(
                        "Blocked native handoff changed another execution"
                    )
                authority_info = json.loads(command("docker", "inspect", context_name))[
                    0
                ]
                if authority_info["HostConfig"]["Privileged"] or any(
                    "docker.sock" in mount["Destination"]
                    for mount in authority_info["Mounts"]
                ):
                    raise RuntimeError("Context gained a host manager/socket")
                report.update(
                    passed=True,
                    native_launch_path_tested=True,
                    native_concurrency_verified=True,
                    logical_holds_retained=10,
                    single_use_workers_spent=10,
                    context_isolated_from_host_manager=True,
                )
            finally:
                for name in names:
                    try:
                        info = json.loads(command("docker", "inspect", name))[0]
                        (output / (name + ".state.json")).write_text(
                            json.dumps(
                                dict(
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
                    except Exception:
                        pass
                for name in reversed(names):
                    subprocess.run(
                        ["docker", "rm", "--force", name],
                        capture_output=True,
                        timeout=20,
                    )
                for network in networks:
                    subprocess.run(
                        ["docker", "network", "rm", network],
                        capture_output=True,
                        timeout=20,
                    )
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], output=str(output), error=report.get("error"))
        ),
        flush=True,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
