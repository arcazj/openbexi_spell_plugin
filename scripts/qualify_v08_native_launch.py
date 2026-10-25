"""Actual retained native launch cohort, not full v0.8/release qualification.

The trusted host provisions ten isolated single-use containers. Each agent uses
real mTLS preflight/consumption against Context before opening a native Listener,
Context and Executor. No Docker socket/host manager enters a worker or Context.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import argparse
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


def pki(directory, *, extra_peers=()):
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
        "subjectAltName=DNS:localhost,DNS:context,DNS:listener,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth,clientAuth\n"
    )
    peers = {}
    for name in ["context", "listener", *extra_peers] + [
        "worker-" + str(n) for n in range(10)
    ]:
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


def await_event(names, event, seconds=90, *, minimum=1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        all_ready = True
        for name in names:
            records = events(name)
            if any(r["event"] == "native-worker-failed" for r in records):
                raise RuntimeError("Native worker failed before " + event)
            if sum(r["event"] == event for r in records) < minimum:
                state = json.loads(command("docker", "inspect", name))[0]["State"]
                if not state["Running"]:
                    raise RuntimeError("Native worker stopped before " + event)
                all_ready = False
        if all_ready:
            return
        time.sleep(0.1)
    raise TimeoutError("Native cohort did not reach " + event)


def host_processes(name, *, executors=1):
    lines = command("docker", "top", name, "-eo", "pid,comm").splitlines()[1:]
    rows = []
    for line in lines:
        pid, executable = line.split(maxsplit=1)
        if executable.startswith("SPELL-"):
            rows.append(dict(host_pid=int(pid), executable=executable))
    if (
        len(rows) != 2 + executors
        or sum("Executor" in p["executable"] for p in rows) != executors
    ):
        raise RuntimeError("Expected distinct real native Listener/Context/Executor")
    return rows


def family_memory(name, limit_mib):
    """Trusted host reads the worker's actual cgroup-v2 resource accounting."""
    raw = command(
        "docker",
        "exec",
        name,
        "python",
        "-I",
        "-c",
        "import json\nfrom pathlib import Path\n"
        "p=Path('/sys/fs/cgroup')\n"
        "events=dict(line.split() for line in (p/'memory.events').read_text().splitlines())\n"
        "print(json.dumps(dict(peak_bytes=int((p/'memory.peak').read_text()),"
        "limit_bytes=int((p/'memory.max').read_text()),"
        "oom_events=int(events['oom']),oom_kills=int(events['oom_kill']))))",
    )
    accounting = json.loads(raw)
    if (
        accounting["limit_bytes"] != limit_mib * 1024 * 1024
        # memory.max permits temporary exceedance; memory.peak is telemetry,
        # not a proof that every instantaneous charge stayed below the cap.
        # https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files
        or accounting["peak_bytes"] <= 0
        or accounting["oom_events"] != 0
        or accounting["oom_kills"] != 0
    ):
        raise RuntimeError(
            "Native family memory binding/OOM differs: "
            + json.dumps(accounting, sort_keys=True)
        )
    return accounting


def qualify_native_child_denial(name, report):
    """Independent local clients cannot impersonate the gate or start a root."""
    program = """import os,queue,socket,sys,tempfile
sys.path.insert(0,'/opt/host')
from native import Bridge
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as stream:
    stream.settimeout(2)
    stream.connect('/tmp/native-admission.sock')
    assert stream.recv(16) != b'ALLOW\\n'
with tempfile.TemporaryFile(mode='w+') as log:
    listener=Bridge(9980,dict(os.environ),log,queue.Queue())
    context=None
    try:
        info=listener.exchange('REQ_CTX_INFO','LST',{'ContextName':'example'})
        context=Bridge(int(info['ContextPort']),dict(os.environ),log,queue.Queue())
        first_key=int(context.exchange('REQ_V08_GUI_KEY','CTX')['GuiKey'])
        for operation,fields in (
            ('REQ_GUI_LOGIN',{'Host':'openbexi-host-v1'}),
            ('REQ_OPEN_EXEC',{'ProcId':'child_0#999999999','GuiMode':'CONTROL',
                'Arguments':'{}','OpenMode':'{Automatic:True,Visible:False,Blocking:False}'}),
            ('REQ_CLOSE_EXEC',{'ProcId':'main_0#1'}),
            ('REQ_GUI_LOGOUT',{}),
            ('REQ_CLIENT_INFO',{})):
            try:
                context.exchange(operation,'CTX',fields)
            except RuntimeError as error:
                assert 'V08_CONTEXT_MUTATION_DENIED' in str(error),str(error)
            else:
                raise AssertionError('Foreign Context request was accepted')
        # Host was the first channel. Proposed existing/closed keys must fail
        # before addClient and can never displace its original IPC connection.
        for key in (1,first_key):
            with socket.create_connection(('127.0.0.1',int(info['ContextPort'])),timeout=2) as raw:
                raw.sendall(key.to_bytes(2,'big'))
                try:
                    assert raw.recv(2) == b''
                except ConnectionResetError:
                    pass
        context.close()
        context=Bridge(int(info['ContextPort']),dict(os.environ),log,queue.Queue())
        assert int(context.exchange('REQ_V08_GUI_KEY','CTX')['GuiKey']) > first_key
    finally:
        if context is not None:
            context.close()
        listener.close()
print('native-unadmitted-start-and-peer-denied',flush=True)
"""
    answer = command("docker", "exec", name, "python", "-I", "-c", program)
    if answer.splitlines()[-1] != "native-unadmitted-start-and-peer-denied":
        raise RuntimeError("Native denial probe did not complete")
    host_processes(name)
    report["native_unadmitted_root_denied_before_spawn"] = True
    report["native_same_uid_peer_impersonation_denied"] = True
    report["native_context_gui_boundary"] = dict(
        foreign_requests_denied=5,
        proposed_keys_denied=2,
        connection_keys_never_reused=True,
        native_roster_admission=False,
        boundary="before Context login/management and native addClient",
    )


def qualify_pause_probe(
    controller,
    executions,
    connection,
    control,
    worker_names,
    containers,
    state,
    report,
    *,
    thread_barrier=False,
):
    """Negative native oracle: PAUSED main plus a still-running background thread."""
    target = executions[1]
    counter = "from pathlib import Path;p=Path('/tmp/v08-pause-counter');print(p.read_text() if p.exists() else '0')"
    ready_deadline = time.monotonic() + 5
    while (
        int(command("docker", "exec", worker_names[1], "python", "-I", "-c", counter))
        == 0
    ):
        if time.monotonic() >= ready_deadline:
            raise RuntimeError("Background-thread fixture did not start before pause")
        time.sleep(0.05)
    bob = controller("session.open", {}, "bob")["connection_id"]
    claim = controller(
        "execution.claim",
        dict(execution_id=target["id"], connection_id=bob, expected_epoch=1),
        "bob",
    )
    started = time.monotonic()
    decision = controller(
        "execution.decide",
        dict(
            execution_id=target["id"],
            connection_id=connection,
            expected_epoch=1,
            connection_generation=target["connection_generation"],
            capability=target["capability"],
            claim_id=claim["claim_id"],
            decision="accept",
        ),
    )
    if decision["state"] != "PAUSING" or time.monotonic() - started > 0.75:
        raise RuntimeError("Native pause acceptance did not fence and return promptly")
    deadline = time.monotonic() + 15
    while True:
        rows = controller("execution.list", {})["executions"]
        row = next(r for r in rows if r["id"] == target["id"])
        barrier = row["pause_barrier"]
        if barrier and barrier["state"] != "REQUESTED":
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Native pause diagnostic did not settle")
        time.sleep(0.05)
    await_event([worker_names[1]], "native-pause-unproven", seconds=5)
    thread_evidence = None
    if thread_barrier:
        await_event([worker_names[1]], "native-thread-barrier", seconds=5)
        thread_evidence = next(
            e for e in events(worker_names[1]) if e["event"] == "native-thread-barrier"
        )
        if (
            thread_evidence["observed_background_threads"] != 1
            or thread_evidence["acknowledged_background_threads"] != 1
            or thread_evidence["observed_threads_held"] is not True
            or thread_evidence["quiescence_proven"] is not False
            or thread_evidence["barrier_id"] != decision["barrier_id"]
        ):
            raise RuntimeError("Cooperative background thread acknowledgment differs")
        binding = command(
            "docker",
            "exec",
            worker_names[1],
            "python",
            "-I",
            "-c",
            "from pathlib import Path;rows=[r.split()[1] for r in Path('/proc/net/tcp').read_text().splitlines()[1:] if r.split()[3]=='0A' and r.split()[1].endswith(':'+format(36991,'04X'))];assert rows==['0100007F:'+format(36991,'04X')];print('loopback-only')",
        )
        if binding != "loopback-only":
            raise RuntimeError("Cooperative helper is not private loopback")
        report["thread_barrier_loopback_only"] = True
    if (
        barrier["state"] != "UNPROVEN"
        or barrier["report"]["native_status"] != "PAUSED"
        or barrier["quiescence_proven"]
        or barrier["effective_transfer"]
        or row["owner"] != "alice"
        or row["epoch"] != 1
        or row["control_state"] != "RECOVERY_REQUIRED"
    ):
        raise RuntimeError(
            "Native main status was mistaken for safe ownership transfer"
        )
    before = int(
        command("docker", "exec", worker_names[1], "python", "-I", "-c", counter)
    )
    latencies = []
    for _ in range(10):
        started = time.monotonic()
        rows = controller("execution.list", {})["executions"]
        latencies.append(time.monotonic() - started)
        if any(
            r["owner"] != "alice" or r["control_state"] != "OWNED"
            for r in rows
            if r["id"] != target["id"]
        ):
            raise RuntimeError("B's pause barrier changed an unrelated execution")
    time.sleep(0.25)
    after = int(
        command("docker", "exec", worker_names[1], "python", "-I", "-c", counter)
    )
    if (after != before if thread_barrier else after <= before) or max(
        latencies
    ) > 0.75:
        raise RuntimeError(
            "Background-thread or unrelated-controller oracle did not hold"
        )
    report["native_pause_probe"] = dict(
        state="UNPROVEN",
        native_main_status="PAUSED",
        background_counter_before=before,
        background_counter_after=after,
        background_thread_survives_main_pause=not thread_barrier,
        observed_background_thread_held=thread_barrier,
        thread_barrier=thread_evidence,
        unrelated_controller_max_latency_seconds=max(latencies),
        owner_preserved=True,
        epoch_preserved=True,
        quiescence_proven=False,
        effective_transfer=False,
    )
    # Authorized independent host teardown for qualification, never controller
    # disconnect, inferred pause proof, hold release, or production recovery.
    command("docker", "stop", "--time", "3", worker_names[1], timeout=12)
    (control / "finish").write_text("finish unaffected fixtures\n")
    with ThreadPoolExecutor(max_workers=9) as pool:
        exits = list(
            pool.map(
                lambda n: command("docker", "wait", n, timeout=90),
                [n for i, n in enumerate(worker_names) if i != 1],
            )
        )
    if exits != ["0"] * 9:
        raise RuntimeError("An unaffected native procedure did not finish")
    for index, (name, container, execution) in enumerate(
        zip(worker_names, containers, executions, strict=True)
    ):
        info = json.loads(command("docker", "inspect", name))[0]
        records = events(name)
        if (
            info["State"]["Running"]
            or info["State"]["OOMKilled"]
            or info["HostConfig"]["Privileged"]
            or not info["HostConfig"]["ReadonlyRootfs"]
            or info["Image"] != IMAGE
        ):
            raise RuntimeError(
                "Native pause probe worker isolation/termination differs"
            )
        if index != 1 and not any(e["event"] == "native-finished" for e in records):
            raise RuntimeError("An unrelated worker lacks a real completion")
        report["workers"].append(
            dict(
                container=container,
                execution_id=execution["id"],
                events=records,
                whole_container_terminated=True,
                host_teardown_only=index == 1,
                image=info["Image"],
                privileged=False,
                readonly_root=True,
            )
        )
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        if (
            db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] != 10
            or db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] != 10
        ):
            raise RuntimeError("Native pause/host cleanup released a hold")
        event_count = db.execute(
            "SELECT COUNT(*) FROM native_driver_events"
        ).fetchone()[0]
        lifecycle = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT body FROM events WHERE type='NATIVE_DRIVER_EVENT'"
            )
        ]
        for index, execution in enumerate(executions):
            messages = [
                r["message"] for r in lifecycle if r["execution_id"] == execution["id"]
            ]
            if sum(m.startswith("Procedure started:") for m in messages) != 1 or sum(
                m.startswith("Procedure finished:") for m in messages
            ) != (0 if index == 1 else 1):
                raise RuntimeError(
                    "Native pause changed a procedure's lifecycle receipts"
                )
    report.update(
        native_pause_probe_passed=True,
        native_thread_barrier_tested=thread_barrier,
        native_pause_qualified=False,
        native_driver_events_persisted=event_count,
        native_handoff=dict(
            state="BLOCKED",
            owner_preserved=True,
            quiescence_proven=False,
            phase="while_running_pause_attempt",
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dss", action="store_true")
    parser.add_argument("--native-pause-probe", action="store_true")
    parser.add_argument("--native-thread-barrier", action="store_true")
    parser.add_argument("--native-child-gate", action="store_true")
    parser.add_argument("--native-prompts", action="store_true")
    parser.add_argument("--native-terminal", action="store_true")
    parser.add_argument("--native-listener-survival", action="store_true")
    profile = parser.parse_args()
    if (
        sum(
            (
                profile.native_pause_probe,
                profile.native_thread_barrier,
                profile.native_dss,
                profile.native_child_gate,
                profile.native_prompts,
                profile.native_terminal,
                profile.native_listener_survival,
            )
        )
        > 1
    ):
        parser.error(
            "Native pause, cooperative threads and DSS qualify separate profiles"
        )
    profile.native_prompts = profile.native_prompts or profile.native_terminal
    profile.native_child_gate = profile.native_child_gate or profile.native_prompts
    # Prompt qualification must exercise real driver effects against the
    # independently launched DSS, not only Context audit-event RPCs.
    profile.native_dss = profile.native_dss or profile.native_prompts
    profile.native_pause_probe = (
        profile.native_pause_probe or profile.native_thread_barrier
    )
    output = ROOT / ".qualification/v08-native-launch" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    report = dict(
        passed=False,
        native_launch_path_tested=False,
        native_concurrency_verified=False,
        native_pause_qualified=False,
        external_driver_effects_enabled=profile.native_dss,
        native_dss_qualified=False,
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
        ROOT / "host_runtime/python/thread_barrier.py",
        ROOT / "host_runtime/python/native.py",
        ROOT / "host_runtime/python/child_gate.py",
        ROOT / "host_runtime/python/control_journal.py",
        ROOT / "host_runtime/python/prompt_replies.py",
        ROOT / "scripts/v08_prompt_cohort.py",
        ROOT / "host_runtime/build_admission_context.py",
        ROOT / "host_runtime/native_prompt_patch.py",
        ROOT / "host_runtime/native_terminal_patch.py",
        ROOT / "host_runtime/python/terminal_probe.py",
        ROOT / "scripts/v08_terminal_cohort.py",
        *sorted((ROOT / "host_runtime/native").glob("*.H")),
        ROOT / "host_runtime/python/children.py",
        Path(__file__),
        ROOT / "scripts/qualify_v08_native_boundary.py",
        ROOT / "scripts/v08_native_consumption.py",
    ]
    if profile.native_listener_survival:
        inputs.append(ROOT / "scripts/v08_listener_survival.py")
    if profile.native_dss:
        inputs.extend((ROOT / "driver_plugin/src").rglob("*.py"))
        inputs.extend((ROOT / "src/dss").rglob("*.py"))
        inputs.extend((ROOT / "src/dss/data").glob("*.json"))
    for path in inputs:
        report["source_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    prefix = "spell-v08-launch-" + uuid.uuid4().hex[:12]
    names, networks = [], []
    worker_names = []
    try:
        with tempfile.TemporaryDirectory(prefix="spell-native-launch-") as temporary:
            temporary = Path(temporary)
            try:
                if os.getuid() == 0:
                    raise RuntimeError(
                        "Qualification must run as a non-root host operator"
                    )
                load_runtime(temporary, output)
                ca, peers = pki(
                    temporary / "pki",
                    extra_peers=("edge", "observer")
                    if profile.native_listener_survival
                    else (
                        ("worker-probe", "worker-owner", "worker-resume")
                        if profile.native_child_gate
                        else ()
                    ),
                )
                code = temporary / "code"
                package = code / "server/src/openbexi_spell_server"
                package.mkdir(parents=True)
                for path in (ROOT / "server/src/openbexi_spell_server").glob("*.py"):
                    shutil.copy2(path, package / path.name)
                shutil.copy2(
                    ROOT / "host_runtime/python/v08_worker.py", code / "agent.py"
                )
                if profile.native_thread_barrier or profile.native_child_gate:
                    shutil.copy2(
                        ROOT / "host_runtime/python/native.py",
                        code / "native_candidate.py",
                    )
                if profile.native_child_gate:
                    shutil.copy2(
                        ROOT / "host_runtime/python/children.py", code / "children.py"
                    )
                    shutil.copy2(
                        ROOT / "host_runtime/python/prompt_replies.py",
                        code / "prompt_replies.py",
                    )
                    shutil.copy2(
                        ROOT / "host_runtime/python/control_journal.py",
                        code / "control_journal.py",
                    )
                    shutil.copy2(
                        ROOT / "host_runtime/python/child_gate.py",
                        code / "child_gate.py",
                    )
                    shutil.copy2(
                        ROOT / "host_runtime/python/terminal_probe.py",
                        code / "terminal_probe.py",
                    )
                if profile.native_thread_barrier:
                    shutil.copy2(
                        ROOT / "host_runtime/python/thread_barrier.py",
                        code / "thread_barrier.py",
                    )
                    library = code / "native-userlib"
                    library.mkdir()
                    (library / "v08_thread_bootstrap.py").write_text(
                        "import os as _os,sys as _sys\n"
                        "_sys.path.insert(0,'/v08')\n"
                        "from thread_barrier import ThreadBarrier as _ThreadBarrier\n"
                        "_v08_threads=_ThreadBarrier('/source',_os.environ['OPENBEXI_SPELL_ENTRYPOINT'])\n"
                        "_v08_threads.serve(36991)\n"
                    )
                if profile.native_dss:
                    shutil.copytree(
                        ROOT / "src/dss",
                        code / "src/dss",
                        ignore=shutil.ignore_patterns("__pycache__"),
                    )
                    shutil.copytree(
                        ROOT / "driver_plugin/src",
                        code / "driver_plugin/src",
                        ignore=shutil.ignore_patterns("__pycache__"),
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
                worker_image = IMAGE
                if profile.native_child_gate:
                    native_build = temporary / "native-build"
                    native_build.mkdir()
                    for header in (ROOT / "host_runtime/native").glob("*.H"):
                        shutil.copy2(header, native_build / header.name)
                    shutil.copy2(
                        ROOT / "host_runtime/build_admission_context.py",
                        native_build / "build.py",
                    )
                    # Ship the exact opt-in composition module with the builder.
                    # Existing child cohorts do not pass --native-prompts and
                    # retain their original closed prompt mutation policy.
                    shutil.copy2(
                        ROOT / "host_runtime/native_prompt_patch.py",
                        native_build / "native_prompt_patch.py",
                    )
                    shutil.copy2(
                        ROOT / "host_runtime/native_terminal_patch.py",
                        native_build / "native_terminal_patch.py",
                    )
                    (native_build / "Dockerfile").write_text(
                        "FROM " + base + "\nUSER root\n"
                        "RUN apt-get update && apt-get install -y --no-install-recommends g++ nlohmann-json3-dev libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev\n"
                        "COPY *.H build.py native_prompt_patch.py native_terminal_patch.py /candidate/\n"
                        "RUN python /candidate/build.py"
                        + (" --native-prompts" if profile.native_prompts else "")
                        + (" --native-terminal" if profile.native_terminal else "")
                        + "\nUSER 10003:10003\n"
                    )
                    built = subprocess.run(
                        [
                            "docker",
                            "build",
                            "-t",
                            prefix + "-native-child",
                            str(native_build),
                        ],
                        capture_output=True,
                        timeout=900,
                    )
                    (output / "native-context-build.log").write_bytes(
                        built.stdout + built.stderr
                    )
                    if built.returncode:
                        raise RuntimeError("Native before-spawn Context build failed")
                    worker_image = command(
                        "docker",
                        "image",
                        "inspect",
                        "--format",
                        "{{.Id}}",
                        prefix + "-native-child",
                    )
                    report["candidate_worker_image"] = worker_image
                    report["native_context_build"] = json.loads(
                        command(
                            "docker",
                            "run",
                            "--rm",
                            "--network",
                            "none",
                            "--entrypoint",
                            "cat",
                            worker_image,
                            "/opt/v08-native-home/build.json",
                        )
                    )
                sources, snapshot = temporary / "git", temporary / "snapshot"
                sources.mkdir()
                command("git", "init", "-q", sources)
                fixture = "import os,time\ndeadline=time.monotonic()+40\nwhile not os.path.exists('/control/finish'):\n    if time.monotonic()>deadline:raise RuntimeError('finish barrier expired')\n    time.sleep(0.05)\nRESULT={index}*{index}\nassert RESULT == {square}\n"
                if profile.native_listener_survival:
                    fixture = fixture.replace(
                        "deadline=time.monotonic()+40",
                        "counter=0\ndeadline=time.monotonic()+75",
                    )
                    fixture = fixture.replace(
                        "    time.sleep(0.05)\n",
                        "    counter+=1\n"
                        "    with open('/tmp/listener-progress.next','w') as f:f.write(str(counter))\n"
                        "    os.replace('/tmp/listener-progress.next','/tmp/listener-progress')\n"
                        "    time.sleep(0.05)\n",
                    )
                if profile.native_pause_probe:
                    background = (
                        "import threading\n"
                        "def background():\n"
                        "    counter=0\n"
                        "    while not os.path.exists('/control/finish'):\n"
                        "        counter+=1\n"
                        "        with open('/tmp/v08-pause-counter.next','w') as f:f.write(str(counter))\n"
                        "        os.replace('/tmp/v08-pause-counter.next','/tmp/v08-pause-counter')\n"
                        "        time.sleep(0.02)\n"
                        "threading.Thread(target=background,daemon=True).start()\n"
                    )
                if profile.native_dss:
                    fixture += (
                        "from spell.lang.functions import Send,GetTM\n"
                        "assert Send(command='CMD1',Timeout=2,HandleError=False,PromptUser=False,Confirm=False) is True\n"
                        "assert GetTM('TM.POWER.BUS_VOLTAGE',Wait=False,Timeout=2,HandleError=False) == 28.0\n"
                    )
                if profile.native_child_gate:
                    fixture += (
                        "from spell.lang.functions import StartProc\n"
                        "assert StartProc('child_{index}',args=[['INDEX',{index}]],Automatic=True,Visible=({index}%2==0),Blocking=True,HandleError=False) is True\n"
                    )
                    for n in range(10):
                        (sources / ("child_" + str(n) + ".py")).write_text(
                            "import os,time\n"
                            "from spell.runtime import ARGS\nassert ARGS['INDEX'] == "
                            + str(n)
                            + "\n"
                            + (
                                "deadline=time.monotonic()+75\n"
                                "while not os.path.exists('/control/nested-start'):\n"
                                "    if time.monotonic()>deadline:raise RuntimeError('nested barrier expired')\n"
                                "    time.sleep(0.05)\n"
                                "from spell.lang.functions import StartProc\n"
                                "assert StartProc('grandchild_0',args=[['INDEX',100]],Automatic=True,Visible=True,Blocking=True,HandleError=False) is True\n"
                                if n == 0
                                else ""
                            )
                            + "deadline=time.monotonic()+75\n"
                            "while not os.path.exists('/control/child-finish'):\n"
                            "    if time.monotonic()>deadline:raise RuntimeError('child barrier expired')\n"
                            "    time.sleep(0.05)\n"
                        )
                    (sources / "owner_resume.py").write_text(
                        "import os,time\nFIRST = 1\n"
                        "with open('/workspace/owner-running','w') as marker:marker.write('running')\n"
                        "while not os.path.exists('/control/owner-resume'):\n    time.sleep(0.05)\n"
                        "SECOND = 2\n"
                        "with open('/workspace/owner-resumed','w') as marker:marker.write('resumed')\n"
                    )
                    (sources / "owner_probe.py").write_text(
                        "FIRST = 1\nSECOND = 2\nTHIRD = 3\n"
                    )
                    (sources / "consume_probe.py").write_text(
                        "with open('/workspace/consume-probe-ran','w') as marker:marker.write('UNSAFE')\n"
                    )
                    (sources / "grandchild_0.py").write_text(
                        "import os,time\n"
                        "from spell.runtime import ARGS\nassert ARGS['INDEX'] == 100\n"
                        "deadline=time.monotonic()+75\n"
                        "while not os.path.exists('/control/child-finish'):\n"
                        "    if time.monotonic()>deadline:raise RuntimeError('grandchild barrier expired')\n"
                        "    time.sleep(0.05)\n"
                    )
                if profile.native_prompts:
                    from v08_prompt_cohort import prompt_fixture

                    for child in sources.glob("*child*.py"):
                        child.write_text(child.read_text() + prompt_fixture())
                for n in range(10):
                    selected = fixture
                    if profile.native_pause_probe and n == 1:
                        selected = selected.replace(
                            "import os,time\n", "import os,time\n" + background
                        )
                    if profile.native_prompts:
                        selected += prompt_fixture(timeout=(n == 0))
                    (sources / ("procedure_" + str(n) + ".py")).write_text(
                        selected.replace("{index}", str(n)).replace(
                            "{square}", str(n * n)
                        )
                    )
                if profile.native_terminal:
                    from v08_terminal_cohort import CASES, terminal_fixture

                    for case in CASES:
                        (
                            sources / ("terminal_" + case.replace("-", "_") + ".py")
                        ).write_text(terminal_fixture(case))
                    (sources / "terminal_child.py").write_text(
                        terminal_fixture("abort-running")
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
                        runtime_image=worker_image,
                        driver_binding="simulator"
                        if profile.native_dss
                        else "context-audit",
                        aliases=[],
                    )
                    for n in range(10)
                }
                if profile.native_child_gate:
                    for n in range(10):
                        catalog["child-" + str(n)] = dict(
                            catalog["procedure-" + str(n)],
                            entrypoint="child_" + str(n) + ".py",
                        )
                    catalog["grandchild-0"] = dict(
                        catalog["procedure-0"], entrypoint="grandchild_0.py"
                    )
                    catalog["owner-resume"] = dict(
                        catalog["procedure-0"], entrypoint="owner_resume.py"
                    )
                    catalog["owner-probe"] = dict(
                        catalog["procedure-0"], entrypoint="owner_probe.py"
                    )
                    catalog["consume-probe"] = dict(
                        catalog["procedure-0"], entrypoint="consume_probe.py"
                    )
                if profile.native_terminal:
                    for case in CASES:
                        catalog["terminal-" + case] = dict(
                            catalog["procedure-0"],
                            entrypoint="terminal_" + case.replace("-", "_") + ".py",
                        )
                    catalog["terminal-child"] = dict(
                        catalog["procedure-0"], entrypoint="terminal_child.py"
                    )
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
                if profile.native_pause_probe:
                    config["native_pause"] = "fenced-probe"
                if profile.native_child_gate:
                    config["native_children"] = "admission-only"
                    config["native_controls"] = "run-journal"
                if profile.native_prompts:
                    config["native_prompts"] = "owner-reply-candidate"
                if profile.native_listener_survival:
                    config["subjects"]["observer"] = ["context:read", "execution:read"]
                dss_name = None
                driver_network = None
                if profile.native_dss:
                    driver_network = prefix + "-driver-net"
                    command("docker", "network", "create", "--internal", driver_network)
                    networks.append(driver_network)
                    dss_name = prefix + "-dss"
                    dss_program = (
                        "import json,os,signal,threading,time\n"
                        "from dss.engine import DssEngine\n"
                        "from dss.local import LocalRuntime\n"
                        "from dss.server import ApiServer,TcServer\n"
                        "runtime=LocalRuntime(DssEngine('/state/dss.sqlite3'),bootstrap_servers='unused.local:9092')\n"
                        "tcp=TcServer(('0.0.0.0',4545),runtime);runtime.tc_address=tcp.server_address\n"
                        "api=ApiServer(('0.0.0.0',8085),runtime)\n"
                        "for s in (tcp,api):threading.Thread(target=s.serve_forever,daemon=True).start()\n"
                        "print(json.dumps({'ready':True,'pid':os.getpid()}),flush=True)\n"
                        "while True:time.sleep(1);runtime.engine.advance()\n"
                    )
                    names.append(dss_name)
                    command(
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        dss_name,
                        "--init",
                        "--read-only",
                        "--network",
                        driver_network,
                        "--cap-drop",
                        "ALL",
                        "--security-opt",
                        "no-new-privileges",
                        "--pids-limit",
                        "64",
                        "--memory",
                        "256m",
                        "--cpu-shares",
                        "2048",
                        "--user",
                        "10003:10003",
                        "--tmpfs",
                        "/state:rw,nosuid,nodev,size=32m,uid=10003,gid=10003",
                        "--mount",
                        f"type=bind,src={code},dst=/v08,readonly",
                        "--env",
                        "PYTHONPATH=/v08/src",
                        "--entrypoint",
                        "python",
                        IMAGE,
                        "-c",
                        dss_program,
                    )
                    dss_info = json.loads(command("docker", "inspect", dss_name))[0]
                    if dss_info["HostConfig"]["CpuShares"] != 2048:
                        raise RuntimeError("DSS CPU resource profile differs")
                    dss_ip = dss_info["NetworkSettings"]["Networks"][driver_network][
                        "IPAddress"
                    ]
                    config["native_driver"] = dict(
                        binding="simulator",
                        url=f"http://{dss_ip}:8085",
                        tcp=[dss_ip, 4545],
                        directory="/state/driver",
                        commands=["CMD1"],
                        telemetry=["TM.POWER.BUS_VOLTAGE"],
                    )
                    report["dss_container"] = dss_info["Id"]
                    report["dss_profile"] = (
                        "isolated synthetic binary TCP and HTTP; no Kafka"
                    )
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            command(
                                "docker",
                                "exec",
                                dss_name,
                                "python",
                                "-c",
                                "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8085/api/v1/state',timeout=1).read()",
                            )
                            break
                        except RuntimeError:
                            if time.monotonic() >= deadline:
                                raise RuntimeError("Isolated DSS startup failed")
                            time.sleep(0.1)
                (secure / "config.json").write_bytes(canonical(config))
                context_name = prefix + "-context"
                args = [
                    "docker",
                    "create",
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
                    "--cpu-shares",
                    "2048",
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
                        "PYTHONPATH=/v08/server/src:/v08/driver_plugin/src:/v08/src"
                        if profile.native_dss
                        else "PYTHONPATH=/v08/server/src",
                        "--entrypoint",
                        "python",
                        context_image,
                        "-m",
                        "openbexi_spell_dss.context_server"
                        if profile.native_dss
                        else "openbexi_spell_server",
                        "context",
                        "--config",
                        "/credentials/config.json",
                    ]
                )
                names.append(context_name)
                command(*args)
                if driver_network is not None:
                    command(
                        "docker", "network", "connect", driver_network, context_name
                    )
                command("docker", "start", context_name)
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
                # The nested worker has three native Executors; the other
                # family workers have two. The old one-Executor 768 MiB cap
                # OOM-killed a child in the dev32 PR cohort. These are bounded
                # qualification resources, not a production admission claim.
                memory_limits = [
                    (1536 if n == 0 else 1024) if profile.native_child_gate else 768
                    for n in range(10)
                ]
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
                                **(
                                    {"pause_probe": True}
                                    if profile.native_pause_probe
                                    else {}
                                ),
                                **(
                                    {"thread_barrier_probe": True}
                                    if profile.native_thread_barrier
                                    else {}
                                ),
                                **(
                                    {
                                        "native_child_gate": True,
                                        **(
                                            {"native_prompt_gate": True}
                                            if profile.native_prompts
                                            else {}
                                        ),
                                    }
                                    if profile.native_child_gate
                                    else {}
                                ),
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
                        str(memory_limits[n]) + "m",
                        "--cpus",
                        "2",
                        "--cpu-shares",
                        "128",
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
                            worker_image,
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
                if profile.native_child_gate:
                    qualify_native_child_denial(worker_names[0], report)
                report["paused_cohort"] = [
                    {"container": container, "processes": host_processes(name)}
                    for name, container in zip(worker_names, containers, strict=True)
                ]
                prompt_cohort = None
                if profile.native_prompts:
                    from v08_prompt_cohort import PromptCohort

                    prompt_cohort = PromptCohort(
                        state, controller, executions, connection
                    )
                    prompt_cohort.start()
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
                if profile.native_listener_survival:
                    from v08_listener_survival import qualify_listener_survival

                    qualify_listener_survival(
                        directory=temporary,
                        code=code,
                        ca=ca,
                        peers=peers,
                        context_name=context_name,
                        context_image=context_image,
                        control_network=control_network,
                        state=state,
                        worker_names=worker_names,
                        names=names,
                        report=report,
                        command=command,
                        host_processes=host_processes,
                    )
                if profile.native_pause_probe:
                    qualify_pause_probe(
                        controller,
                        executions,
                        connection,
                        control,
                        worker_names,
                        containers,
                        state,
                        report,
                        thread_barrier=profile.native_thread_barrier,
                    )
                else:
                    (control / "finish").write_text("finish fixture\n")
                    if profile.native_child_gate:
                        await_event(worker_names, "native-child-running", seconds=70)
                        processes = [
                            host_processes(name, executors=2) for name in worker_names
                        ]
                        if (
                            len({p["host_pid"] for group in processes for p in group})
                            != 40
                        ):
                            raise RuntimeError(
                                "Native child cohort lacks forty distinct PIDs"
                            )
                        report["native_child_cohort_pids"] = 40
                        (control / "nested-start").write_text("start grandchild once\n")
                        await_event(
                            [worker_names[0]],
                            "native-child-running",
                            seconds=30,
                            minimum=2,
                        )
                        processes = [
                            host_processes(name, executors=3 if index == 0 else 2)
                            for index, name in enumerate(worker_names)
                        ]
                        if (
                            len({p["host_pid"] for group in processes for p in group})
                            != 41
                        ):
                            raise RuntimeError(
                                "Nested native cohort lacks forty-one PIDs"
                            )
                        report["native_child_cohort_pids"] = 41
                        with ThreadPoolExecutor(max_workers=10) as pool:
                            report["native_family_memory"] = list(
                                pool.map(family_memory, worker_names, memory_limits)
                            )
                        (control / "child-finish").write_text(
                            "finish native children\n"
                        )
                    with ThreadPoolExecutor(max_workers=10) as pool:
                        exits = list(
                            pool.map(
                                lambda name: command(
                                    "docker", "wait", name, timeout=90
                                ),
                                worker_names,
                            )
                        )
                    if prompt_cohort is not None:
                        report["native_prompt_cohort"] = prompt_cohort.finish()
                    if exits != ["0"] * 10:
                        raise RuntimeError("Native cohort did not exit successfully")
                    for name, container, execution in zip(
                        worker_names, containers, executions, strict=True
                    ):
                        records = events(name)
                        if not any(
                            r["event"] == "native-finished"
                            and (
                                not profile.native_child_gate
                                or r.get("native_lifecycle_receipts_settled") is True
                            )
                            for r in records
                        ):
                            raise RuntimeError("Native completion evidence absent")
                        info = json.loads(command("docker", "inspect", name))[0]
                        if (
                            info["State"]["Running"]
                            or info["State"]["OOMKilled"]
                            or info["HostConfig"]["Privileged"]
                            or info["HostConfig"]["CpuShares"] != 128
                            or info["HostConfig"]["Memory"]
                            != memory_limits[worker_names.index(name)] * 1024 * 1024
                            or not info["HostConfig"]["ReadonlyRootfs"]
                            or info["Image"] != worker_image
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
                    if profile.native_dss:
                        # A copied ORIGINAL config must not be enough to skip
                        # consumption and use the driver's effect route directly.
                        # The single winner's consumption proof is memory-only.
                        attacker = prefix + "-driver-clone"
                        probe_command = list(launch_commands[1])
                        probe_command[probe_command.index("--name") + 1] = attacker
                        probe = (
                            "import base64,json,sys,uuid\n"
                            "sys.path.insert(0,'/v08/server/src')\n"
                            "from openbexi_spell_server.transport import Route,tls_context\n"
                            "from openbexi_spell_server.contracts import Fault\n"
                            "from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p\n"
                            "c=json.load(open('/credentials/config.json'));w=c['preflight']\n"
                            "r=Route(w['context_url'],w['context_fingerprint'],tls_context(w['ca'],w['certificate'],w['key']))\n"
                            "payload=base64.b64encode(p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1')).SerializeToString()).decode('ascii')\n"
                            "b=dict(schema='openbexi.worker/2',context_id=w['context_id'],grant=c['grant'],request_id=str(uuid.uuid4()),path='/spell.driver.SPELLDriverInterface_TC/SendCommand',payload=payload)\n"
                            "try:r.call(b,path='/v1/worker/driver',schema='openbexi.worker/2')\n"
                            "except Fault as e:\n"
                            " if e.code!='context_request_denied' or e.status!=403:raise\n"
                            "else:raise RuntimeError('Copied original config gained driver authority')\n"
                            "print('copied-original-driver-config-denied',flush=True)\n"
                        )
                        probe_command[probe_command.index("-I") :] = ["-I", "-c", probe]
                        names.append(attacker)
                        command(*probe_command)
                        if command("docker", "wait", attacker, timeout=15) != "0":
                            raise RuntimeError(
                                "Copied original config bypassed consumption proof"
                            )
                        report["copied_original_driver_config_denied"] = True
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
                            "file:" + str(state / "context.sqlite3") + "?mode=ro",
                            uri=True,
                        )
                    ) as audit:
                        if audit.execute("SELECT SUM(spent) FROM workers").fetchone()[
                            0
                        ] != 10 or audit.execute(
                            "SELECT COUNT(*) FROM reservations"
                        ).fetchone()[0] != (21 if profile.native_child_gate else 10):
                            raise RuntimeError(
                                "Native completion released a hold or worker slot"
                            )
                    with closing(
                        sqlite3.connect(
                            "file:" + str(state / "context.sqlite3") + "?mode=ro",
                            uri=True,
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
                        report["native_lifecycle_counts"] = []
                        for index, execution in enumerate(executions):
                            messages = [
                                body["message"]
                                for body in bodies
                                if body["execution_id"] == execution["id"]
                            ]
                            started = sum(
                                message.startswith("Procedure started:")
                                for message in messages
                            )
                            finished = sum(
                                message.startswith("Procedure finished:")
                                for message in messages
                            )
                            # Every candidate automatic child now enters its
                            # normal initial pause and admitted RUN, including
                            # hidden children. Each must emit one real start/end.
                            expected_started = 2 if profile.native_child_gate else 1
                            expected_finished = 2 if profile.native_child_gate else 1
                            if profile.native_child_gate and index == 0:
                                expected_started += 1
                                expected_finished += 1
                            report["native_lifecycle_counts"].append(
                                dict(
                                    worker_index=index,
                                    started=started,
                                    finished=finished,
                                    expected_started=expected_started,
                                    expected_finished=expected_finished,
                                )
                            )
                            if (
                                started != expected_started
                                or finished != expected_finished
                            ):
                                raise RuntimeError(
                                    "Native lifecycle events lack unique durable receipts"
                                )
                        if (profile.native_child_gate and event_count != 42) or (
                            not profile.native_child_gate and event_count < 20
                        ):
                            raise RuntimeError(
                                "Native lifecycle events lack durable receipts"
                            )
                    report["native_driver_events_persisted"] = event_count
                    if profile.native_child_gate:
                        with closing(
                            sqlite3.connect(
                                "file:" + str(state / "context.sqlite3") + "?mode=ro",
                                uri=True,
                            )
                        ) as audit:
                            child_states = audit.execute(
                                "SELECT state,COUNT(*) FROM child_admissions GROUP BY state"
                            ).fetchall()
                            if child_states != [("CONSUMED", 11)]:
                                raise RuntimeError(
                                    "Native children lack eleven consumed Context admissions"
                                )
                            nested = audit.execute(
                                "SELECT c.state,p.state,c.execution_id=p.execution_id "
                                "FROM child_admissions c JOIN child_admissions p ON c.parent_id=p.id "
                                "WHERE c.parent_id IS NOT NULL"
                            ).fetchall()
                            if nested != [("CONSUMED", "CONSUMED", 1)]:
                                raise RuntimeError(
                                    "Nested native admission lacks its original consumed parent"
                                )
                            controls = audit.execute(
                                "SELECT state,outcome,COUNT(*) FROM native_control_attempts "
                                "GROUP BY state,outcome"
                            ).fetchall()
                            # Ten roots, ten visible/hidden children and one
                            # visible grandchild all require admitted initial RUN.
                            if controls != [
                                ("DISPATCH_UNCERTAIN", "IPC_SEND_ACKNOWLEDGED", 21)
                            ]:
                                raise RuntimeError(
                                    "Native agent RUN attempts lack exact durable receipts"
                                )
                            forwards = audit.execute(
                                "SELECT state,COUNT(*) FROM native_control_forwards GROUP BY state"
                            ).fetchall()
                            if forwards != [("FORWARD_UNPROVEN", 21)]:
                                raise RuntimeError(
                                    "Native RUN bypassed one-shot before-forward admission"
                                )
                            if (
                                audit.execute(
                                    "SELECT COUNT(*) FROM native_control_forwards f "
                                    "JOIN native_control_attempts a ON f.request_id=a.request_id "
                                    "WHERE f.execution_id=a.execution_id AND f.origin_hash=a.origin_hash "
                                    "AND f.operation_digest=a.operation_digest"
                                ).fetchone()[0]
                                != 21
                            ):
                                raise RuntimeError(
                                    "Native RUN forward lost original journal identity"
                                )
                            consumptions = audit.execute(
                                "SELECT state,COUNT(*) FROM native_control_consumptions GROUP BY state"
                            ).fetchall()
                            if consumptions != [("EXECUTION_UNPROVEN", 21)]:
                                raise RuntimeError(
                                    "Native RUN bypassed Executor consumption admission"
                                )
                            # The actual native Executor now emits a one-shot
                            # mailbox observation for every completed handler.
                            # This remains neither external-effect settlement nor
                            # proof of full-family quiescence.
                            dispositions = audit.execute(
                                "SELECT disposition,COUNT(*) FROM native_control_dispositions "
                                "GROUP BY disposition"
                            ).fetchall()
                            if dispositions != [("HANDLER_RETURNED", 21)]:
                                raise RuntimeError(
                                    "Original native Executor mailbox return evidence differs"
                                )
                            if (
                                audit.execute(
                                    "SELECT COUNT(*) FROM native_control_dispositions d "
                                    "JOIN native_control_consumptions c "
                                    "ON d.request_id=c.request_id AND d.execution_id=c.execution_id "
                                    "WHERE c.state='EXECUTION_UNPROVEN'"
                                ).fetchone()[0]
                                != 21
                            ):
                                raise RuntimeError(
                                    "Native mailbox observations lost original consumption identity"
                                )
                            members = audit.execute(
                                "SELECT state,COUNT(*) FROM native_members GROUP BY state"
                            ).fetchall()
                            if (
                                members != [("REGISTERED_UNPROVEN", 21)]
                                or audit.execute(
                                    "SELECT COUNT(*) FROM native_members m JOIN native_control_attempts a "
                                    "ON m.execution_id=a.execution_id AND m.target_id=a.target_id "
                                    "WHERE m.origin_hash=a.origin_hash"
                                ).fetchone()[0]
                                != 21
                            ):
                                raise RuntimeError(
                                    "Native RUN lacks its original durable member binding"
                                )
                            if (
                                audit.execute(
                                    "SELECT COUNT(*) FROM native_control_consumptions c "
                                    "JOIN native_control_forwards f ON c.request_id=f.request_id "
                                    "WHERE c.execution_id=f.execution_id AND c.origin_hash=f.origin_hash "
                                    "AND c.operation_digest=f.operation_digest"
                                ).fetchone()[0]
                                != 21
                            ):
                                raise RuntimeError(
                                    "Native RUN consumption lost original forward identity"
                                )
                            if (
                                audit.execute(
                                    "SELECT COUNT(*) FROM native_control_attempts c "
                                    "JOIN child_admissions a ON c.target_id=a.id "
                                    "WHERE c.execution_id=a.execution_id AND c.origin_hash=a.origin_hash"
                                ).fetchone()[0]
                                != 11
                            ):
                                raise RuntimeError(
                                    "Native child RUN attempt has a different family origin"
                                )
                        if any(
                            next(
                                e
                                for e in worker["events"]
                                if e["event"] == "native-finished"
                            )["native_children_admitted"]
                            != (2 if index == 0 else 1)
                            for index, worker in enumerate(report["workers"])
                        ):
                            raise RuntimeError(
                                "Native child provider admission counts differ from the family tree"
                            )
                        if (
                            sum(
                                event["event"] == "native-unadmitted-run-denied"
                                for worker in report["workers"]
                                for event in worker["events"]
                            )
                            != 10
                        ):
                            raise RuntimeError(
                                "Native unadmitted RUN denial count differs"
                            )
                        if (
                            sum(
                                event["event"] == "native-executor-bound"
                                for worker in report["workers"]
                                for event in worker["events"]
                            )
                            != 21
                        ):
                            raise RuntimeError(
                                "Native Executor PID binding count differs"
                            )
                        observed_returns = sum(
                            event["event"] == "native-mailbox-disposition-received"
                            and event.get("disposition") == "HANDLER_RETURNED"
                            for worker in report["workers"]
                            for event in worker["events"]
                        )
                        if observed_returns != 21:
                            raise RuntimeError(
                                "Native Executor one-shot mailbox callbacks differ from durable receipts"
                            )
                        report.update(
                            native_initial_run_mailbox_returns_observed=observed_returns,
                            native_initial_mailbox_dispositions_durable=21,
                            native_child_before_spawn_component_tested=True,
                            native_child_admissions_consumed=11,
                            native_nested_child_admissions_consumed=1,
                            full_family_qualified=False,
                            native_agent_run_attempts_journalled=21,
                            native_context_run_forwards_admitted=21,
                            native_executor_run_consumptions_admitted=21,
                            native_executor_pid_bindings=21,
                            native_durable_member_bindings=21,
                            native_members_host_attested=False,
                            native_unadmitted_run_denials=10,
                            native_control_queue_settlement_proven=False,
                        )
                    if profile.native_dss:
                        state_probe = (
                            "import json,urllib.request;"
                            "print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8085/api/v1/state'))['core']))"
                        )
                        actual = json.loads(
                            command(
                                "docker", "exec", dss_name, "python", "-c", state_probe
                            )
                        )
                        if actual["commands_executed"] != 10:
                            raise RuntimeError("Native DSS command count differs")
                        with closing(
                            sqlite3.connect(
                                "file:" + str(state / "context.sqlite3") + "?mode=ro",
                                uri=True,
                            )
                        ) as audit:
                            stages = audit.execute(
                                "SELECT state,COUNT(*) FROM effect_intents GROUP BY state"
                            ).fetchall()
                            if stages != [("ACKED", 50)]:
                                raise RuntimeError(
                                    "Native TC lacks fifty correlated durable stage receipts"
                                )
                            authority_rows = audit.execute(
                                "SELECT * FROM effect_intents ORDER BY operation,stage"
                            ).fetchall()
                            methods = dict(
                                audit.execute(
                                    "SELECT path,COUNT(*) FROM native_driver_calls WHERE state='COMPLETED' GROUP BY path"
                                )
                            )
                            if (
                                methods.get(
                                    "/spell.driver.SPELLDriverInterface_TC/SendCommand"
                                )
                                != 10
                                or methods.get(
                                    "/spell.driver.SPELLDriverInterface_TM/RefreshItem",
                                    0,
                                )
                                < 10
                            ):
                                raise RuntimeError(
                                    "Native original TC/TM method evidence absent"
                                )
                        with closing(
                            sqlite3.connect(
                                "file:"
                                + str(state / "driver/driver.sqlite3")
                                + "?mode=ro",
                                uri=True,
                            )
                        ) as driver_audit:
                            driver_rows = driver_audit.execute(
                                "SELECT * FROM effect_intents ORDER BY operation,stage"
                            ).fetchall()
                        if driver_rows != authority_rows or any(
                            not row[6] for row in driver_rows
                        ):
                            raise RuntimeError(
                                "Native authority and driver receipts differ"
                            )
                        for worker in report["workers"]:
                            finished = next(
                                e
                                for e in worker["events"]
                                if e["event"] == "native-finished"
                            )
                            if not finished["external_driver_effects_enabled"]:
                                raise RuntimeError(
                                    "Worker lacks original command dispatch evidence"
                                )
                        report.update(
                            native_dss_qualified=True,
                            native_dss_commands=10,
                            native_dss_stage_receipts=50,
                            native_dss_driver_stage_receipts=50,
                            native_dss_cross_ledger_match=True,
                            native_dss_receipt_digest=hashlib.sha256(
                                canonical(driver_rows)
                            ).hexdigest(),
                            native_driver_methods=methods,
                        )
                    first_row = next(
                        row for row in retained if row["id"] == first["id"]
                    )
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
                if profile.native_child_gate and not profile.native_terminal:
                    from v08_native_consumption import qualify_consumption_fence

                    qualify_consumption_fence(
                        temporary=temporary,
                        prefix=prefix,
                        context_image=context_image,
                        config=config,
                        sources=sources,
                        worker_image=worker_image,
                        code=code,
                        snapshot=snapshot,
                        ca=ca,
                        peers=peers,
                        primary_controller=controller,
                        control=control,
                        primary_state=state,
                        names=names,
                        networks=networks,
                        report=report,
                        command=command,
                        await_event=await_event,
                        host_processes=host_processes,
                        events=events,
                    )
                    qualify_consumption_fence(
                        owner_commands=True,
                        temporary=temporary,
                        prefix=prefix,
                        context_image=context_image,
                        config=config,
                        sources=sources,
                        worker_image=worker_image,
                        code=code,
                        snapshot=snapshot,
                        ca=ca,
                        peers=peers,
                        primary_controller=controller,
                        control=control,
                        primary_state=state,
                        names=names,
                        networks=networks,
                        report=report,
                        command=command,
                        await_event=await_event,
                        host_processes=host_processes,
                        events=events,
                    )
                    qualify_consumption_fence(
                        owner_resume=True,
                        temporary=temporary,
                        prefix=prefix,
                        context_image=context_image,
                        config=config,
                        sources=sources,
                        worker_image=worker_image,
                        code=code,
                        snapshot=snapshot,
                        ca=ca,
                        peers=peers,
                        primary_controller=controller,
                        control=control,
                        primary_state=state,
                        names=names,
                        networks=networks,
                        report=report,
                        command=command,
                        await_event=await_event,
                        host_processes=host_processes,
                        events=events,
                    )
                if profile.native_terminal:
                    from v08_native_consumption import qualify_consumption_fence

                    for case in CASES:
                        qualify_consumption_fence(
                            terminal_case=case,
                            terminal_evidence=output,
                            temporary=temporary,
                            prefix=prefix,
                            context_image=context_image,
                            config=config,
                            sources=sources,
                            worker_image=worker_image,
                            code=code,
                            snapshot=snapshot,
                            ca=ca,
                            peers=peers,
                            primary_controller=controller,
                            control=control,
                            primary_state=state,
                            names=names,
                            networks=networks,
                            report=report,
                            command=command,
                            await_event=await_event,
                            host_processes=host_processes,
                            events=events,
                        )
                authority_info = json.loads(command("docker", "inspect", context_name))[
                    0
                ]
                if authority_info["HostConfig"]["Privileged"] or any(
                    "docker.sock" in mount["Destination"]
                    for mount in authority_info["Mounts"]
                ):
                    raise RuntimeError("Context gained a host manager/socket")
                if authority_info["HostConfig"]["CpuShares"] != 2048:
                    raise RuntimeError("Context CPU resource profile differs")
                report.update(
                    passed=True,
                    native_launch_path_tested=True,
                    native_concurrency_verified=True,
                    logical_holds_retained=21 if profile.native_child_gate else 10,
                    single_use_workers_spent=10,
                    context_isolated_from_host_manager=True,
                    requested_cpu_shares_verified=dict(
                        context=2048,
                        dss=2048 if profile.native_dss else None,
                        worker=128,
                    ),
                )
            finally:
                if (
                    profile.native_dss
                    and "state" in locals()
                    and (state / "context.sqlite3").is_file()
                ):
                    try:
                        with closing(
                            sqlite3.connect(
                                "file:" + str(state / "context.sqlite3") + "?mode=ro",
                                uri=True,
                            )
                        ) as audit:
                            report["native_driver_failure_categories"] = audit.execute(
                                "SELECT json_extract(body,'$.error_type'),json_extract(body,'$.error_code'),COUNT(*) "
                                "FROM events WHERE type='NATIVE_DRIVER_CALL_FAILED' GROUP BY 1,2"
                            ).fetchall()
                            report["native_driver_failure_chains"] = audit.execute(
                                "SELECT json_extract(body,'$.error_chain'),COUNT(*) "
                                "FROM events WHERE type='NATIVE_DRIVER_CALL_FAILED' GROUP BY 1"
                            ).fetchall()
                            report["native_driver_call_states"] = audit.execute(
                                "SELECT state,COUNT(*) FROM native_driver_calls GROUP BY state"
                            ).fetchall()
                            report["native_driver_stage_states"] = audit.execute(
                                "SELECT state,COUNT(*) FROM effect_intents GROUP BY state"
                            ).fetchall()
                    except sqlite3.Error:
                        report["native_driver_failure_categories_unavailable"] = True
                if (
                    profile.native_child_gate
                    and "state" in locals()
                    and (state / "context.sqlite3").is_file()
                ):
                    try:
                        with closing(
                            sqlite3.connect(
                                "file:" + str(state / "context.sqlite3") + "?mode=ro",
                                uri=True,
                            )
                        ) as audit:
                            report["native_child_authority_states"] = audit.execute(
                                "SELECT state,COUNT(*) FROM child_admissions GROUP BY state"
                            ).fetchall()
                    except sqlite3.Error:
                        report["native_child_authority_states_unavailable"] = True
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
                        if (
                            profile.native_child_gate
                            and info["State"]["Running"]
                            and name in worker_names
                        ):
                            native_logs = command(
                                "docker",
                                "exec",
                                name,
                                "python",
                                "-I",
                                "-c",
                                "from pathlib import Path\n"
                                "for p in list(Path('/tmp').glob('spell-host-*/native.log'))[:2]:\n"
                                " with p.open('rb') as f:\n"
                                "  f.seek(0,2);end=f.tell();f.seek(max(0,end-65536));print(f.read().decode(errors='replace'))\n",
                            )
                            (output / (name + ".native-tail.log")).write_text(
                                native_logs
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
