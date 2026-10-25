"""Rebuild the original native binaries and exercise enabled Step 1 lifecycles.

This is a trusted HOST qualification driver. Only synthetic immutable procedures
are admitted. Worker/Context code receives neither Docker access nor host manager
credentials. Every case uses a fresh Context and single-use container; no retained
worker, grant or native process is relabeled for another execution. Failed cases
remain failed in the source-bound report. This does not authorize owner transfer.
"""

from contextlib import closing
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server/src"))
from openbexi_spell_server.contracts import Fault, canonical, envelope  # noqa: E402
from openbexi_spell_server.transport import Route, tls_context  # noqa: E402
from openbexi_spell_server.worker import preflight  # noqa: E402
from qualify_v08_native_launch import (  # noqa: E402
    IMAGE,
    ARCHIVE_SHA256,
    command,
    pki,
    load_runtime,
    events,
    await_event,
)

CASES = (
    "normal",
    "failure",
    "answer",
    "cancel",
    "timeout",
    "abort-running",
    "abort-prompt",
    "close-running",
    "family",
    "forced-loss",
    "driver",
    "timeout-answer",
    "timeout-cancel",
    "duplicate-prompt",
    "late-prompt",
)
PERMISSIONS = [
    "context:read",
    "execution:read",
    "execution:start",
    "execution:control",
    "execution:request_control",
]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fixture(case):
    start = "import os,time\nfrom pathlib import Path\n"
    marker = "Path('/workspace/body-entered').write_text('entered')\n"
    question = (
        "from spell.lang.functions import Prompt\n"
        "from spell.lang.constants import YES_NO,ALPHA\n"
    )
    if case == "normal":
        body = "RESULT=40+2\nassert RESULT==42\nPath('/workspace/completed').write_text('42')\n"
    elif case == "failure":
        body = (
            "try:\n    raise ValueError('intentional Step 1 failure')\nfinally:\n"
            "    Path('/workspace/unwound').write_text('unwound')\n"
        )
    elif case in {"answer", "duplicate-prompt", "late-prompt"}:
        body = (
            question
            + "answer=Prompt('Step 1 synthetic prompt',Type=YES_NO,HandleError=False)\nassert answer is True\n"
        )
        if case == "late-prompt":
            body += "second=Prompt('Step 1 second generation',Type=YES_NO,HandleError=False)\nassert second is True\n"
        body += (
            "Path('/workspace/answered').write_text('answered')\n"
            "while not os.path.exists('/control/finish'):\n    time.sleep(.02)\n"
        )
    elif case in {"cancel", "abort-prompt"}:
        body = question + (
            "try:\n    Prompt('Step 1 cancellable prompt',Type=YES_NO,HandleError=False)\n"
            "    Path('/workspace/unsafe-after-cancel').write_text('unsafe')\n"
            "finally:\n    Path('/workspace/unwound').write_text('unwound')\n"
        )
    elif case in {"timeout", "timeout-answer", "timeout-cancel"}:
        body = question + (
            "answer=Prompt('Step 1 timed default',Type=ALPHA,Default='fallback',Timeout=1.0,HandleError=False)\n"
            "assert answer=='fallback', repr(answer)\n"
            "Path('/workspace/timed-out').write_text('native-default')\n"
            "while not os.path.exists('/control/finish'):\n    time.sleep(.02)\n"
        )
    elif case in {"abort-running", "close-running", "family", "forced-loss", "driver"}:
        body = ""
        if case == "family":
            body += (
                "import threading,subprocess,sys\n"
                "def background():\n    while True:\n        time.sleep(.02)\n"
                "threading.Thread(target=background,daemon=True).start()\n"
                "subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'],start_new_session=True)\n"
                "from spell.lang.functions import StartProc\n"
                "assert StartProc('child',Automatic=True,Visible=True,Blocking=False,HandleError=False) is True\n"
            )
        if case == "driver":
            body += (
                "from spell.lang.functions import Send\n"
                "assert Send(command='CMD1',Timeout=2,HandleError=False,PromptUser=False,Confirm=False) is True\n"
                "Path('/workspace/driver-sent').write_text('one-command')\n"
            )
        body += (
            "try:\n    while True:\n        time.sleep(.02)\nfinally:\n"
            "    Path('/workspace/unwound').write_text('unwound')\n"
        )
    else:
        raise ValueError("Unrecognized native fixture")
    child = (
        start
        + "Path('/workspace/child-running').write_text('running')\ntry:\n    while True:\n        time.sleep(.02)\nfinally:\n    Path('/workspace/child-unwound').write_text('unwound')\n"
    )
    return start + marker + body, child


def sql(state, statement, values=()):
    with closing(
        sqlite3.connect("file:" + str(state / "context.sqlite3") + "?mode=ro", uri=True)
    ) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(statement, values)]


def wait(name, predicate, description, *, seconds=20, allow_exit=False):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        records = events(name)
        if any(row["event"] == "native-worker-failed" for row in records):
            raise RuntimeError("Native worker failed while waiting for " + description)
        if (
            not allow_exit
            and not json.loads(command("docker", "inspect", name))[0]["State"][
                "Running"
            ]
        ):
            raise RuntimeError("Native worker exited while waiting for " + description)
        time.sleep(0.05)
    raise TimeoutError("Native Step 1 deadline: " + description)


def native_status(name, member):
    matching = [
        r["native_status"]
        for r in events(name)
        if r["event"] == "step1-native-state" and r.get("member") == member
    ]
    return matching[-1] if matching else None


def marker(name, file):
    # Fixed fixture marker paths only; never inspect arbitrary user file contents.
    if file not in {
        "body-entered",
        "completed",
        "unwound",
        "answered",
        "timed-out",
        "unsafe-after-cancel",
        "child-running",
        "child-unwound",
        "driver-sent",
    }:
        raise ValueError("Unknown fixed marker")
    return (
        command(
            "docker",
            "exec",
            name,
            "python",
            "-I",
            "-c",
            "from pathlib import Path; print(int(Path('/workspace/"
            + file
            + "').is_file()))",
        )
        == "1"
    )


def process_inventory(name):
    rows = []
    for line in command("docker", "top", name, "-eo", "pid,comm").splitlines()[1:]:
        identity, executable = line.split(maxsplit=1)
        pid = int(identity)
        try:
            ticks = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        except FileNotFoundError:
            continue
        rows.append(dict(pid=pid, executable=executable, start_ticks=ticks))
    if not any("SPELL-Executor" in r["executable"] for r in rows):
        raise RuntimeError("Original native Executor was not observed independently")
    return rows


def all_gone(rows):
    for row in rows:
        path = Path(f"/proc/{row['pid']}/stat")
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
        except FileNotFoundError:
            continue
        if fields[19] == row["start_ticks"]:
            return False
    return True


def build_native(temporary, output, prefix):
    load_runtime(temporary, output)
    base = prefix + "-frozen"
    command("docker", "tag", IMAGE, base)
    build = temporary / "native-build"
    build.mkdir()
    for path in (ROOT / "host_runtime/native").glob("*.H"):
        shutil.copy2(path, build / path.name)
    for path in (
        "build_admission_context.py",
        "native_prompt_patch.py",
        "native_terminal_patch.py",
    ):
        shutil.copy2(ROOT / "host_runtime" / path, build / path)
    (build / "Dockerfile").write_text(
        "FROM " + base + "\nUSER root\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends git g++ nlohmann-json3-dev libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev\n"
        "COPY *.H *.py /candidate/\n"
        "RUN python /candidate/build_admission_context.py --native-prompts --native-terminals\n"
        "USER 10003:10003\n"
    )
    name = prefix + "-enabled"
    result = subprocess.run(
        ["docker", "build", "-t", name, str(build)], capture_output=True, timeout=1200
    )
    (output / "native-build.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Prompt/terminal-enabled original native build failed")
    image = command("docker", "image", "inspect", "--format", "{{.Id}}", name)
    receipt = json.loads(
        command(
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "cat",
            image,
            "/opt/v08-native-home/build.json",
        )
    )
    if (
        receipt.get("native_prompt_hooks") is not True
        or receipt.get("native_terminal_hooks") is not True
    ):
        raise RuntimeError("Enabled native hooks missing from original build receipt")
    write_json(output / "native-build.json", receipt)
    return image, receipt


def code_mount(temporary):
    code = temporary / "code"
    code.mkdir(mode=0o755)
    shutil.copytree(
        ROOT / "server",
        code / "server",
        ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", "build", "*.egg-info"
        ),
    )
    shutil.copytree(
        ROOT / "driver_plugin/src",
        code / "driver_plugin/src",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(
        ROOT / "src/dss", code / "src/dss", ignore=shutil.ignore_patterns("__pycache__")
    )
    for path in (ROOT / "host_runtime/python").glob("*.py"):
        shutil.copy2(path, code / path.name)
    shutil.copy2(ROOT / "host_runtime/python/native.py", code / "native_candidate.py")
    shutil.copy2(ROOT / "host_runtime/python/v08_worker.py", code / "agent.py")
    return code


def start_dss(prefix, code, image, names, networks):
    network, name = prefix + "-driver", prefix + "-dss"
    command("docker", "network", "create", "--internal", network)
    networks.append(network)
    program = (
        "import threading,time\n"
        "from dss.engine import DssEngine\nfrom dss.local import LocalRuntime\n"
        "from dss.server import ApiServer,TcServer\n"
        "runtime=LocalRuntime(DssEngine('/state/dss.sqlite3'),bootstrap_servers='unused.local:9092')\n"
        "tcp=TcServer(('0.0.0.0',4545),runtime);runtime.tc_address=tcp.server_address\n"
        "api=ApiServer(('0.0.0.0',8085),runtime)\n"
        "threading.Thread(target=tcp.serve_forever,daemon=True).start()\n"
        "threading.Thread(target=api.serve_forever,daemon=True).start()\n"
        "while True:runtime.engine.advance();time.sleep(.02)\n"
    )
    names.append(name)
    command(
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
        "64",
        "--memory",
        "256m",
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
        image,
        "-c",
        program,
    )
    info = json.loads(command("docker", "inspect", name))[0]
    ip = info["NetworkSettings"]["Networks"][network]["IPAddress"]
    end = time.monotonic() + 20
    while True:
        try:
            dss_state(name)
            break
        except Exception:
            if time.monotonic() > end:
                raise RuntimeError("Independent synthetic DSS failed readiness")
            time.sleep(0.1)
    return name, network, ip


def dss_state(name):
    return json.loads(
        command(
            "docker",
            "exec",
            name,
            "python",
            "-I",
            "-c",
            "import json,urllib.request;print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8085/api/v1/state',timeout=2))))",
        )
    )


def run_case(case, root, output, prefix, code, image, ca, peers):
    directory = root / case
    directory.mkdir(mode=0o755)
    names, networks = [], []
    report = dict(
        case=case,
        passed=False,
        native_executor_tested=True,
        hold_retained=True,
        worker_reusable=False,
        ownership_transfer=False,
    )
    name, authority = prefix + "-" + case, prefix + "-" + case + "-context"
    state = directory / "state"
    state.mkdir(mode=0o700)
    original_pids = []
    try:
        sources, snapshot = directory / "git", directory / "snapshot"
        sources.mkdir()
        snapshot.mkdir(mode=0o755)
        body, child = fixture(case)
        for filename, text in (
            ("procedure.py", body),
            ("child.py", child),
            ("witness.py", "assert True\n"),
        ):
            (sources / filename).write_text(text)
            (snapshot / filename).write_text(text)
        command("git", "init", "-q", sources)
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
            "immutable full native Step 1 " + case,
        )
        revision = command("git", "-C", sources, "rev-parse", "HEAD")
        catalog = {
            key: dict(
                repository="/catalog",
                revision=revision,
                entrypoint=entry,
                runtime_image=image,
                driver_binding="simulator" if case == "driver" else "context-audit",
                aliases=[],
            )
            for key, entry in (
                ("main", "procedure.py"),
                ("child", "child.py"),
                ("witness", "witness.py"),
            )
        }
        control = directory / "control"
        control.mkdir(mode=0o755)
        secure = directory / "context-credentials"
        secure.mkdir(mode=0o755)
        private = directory / "worker-credentials"
        private.mkdir(mode=0o755)
        for original, target in (
            (ca, "ca.pem"),
            (peers["context"]["cert"], "context.pem"),
            (peers["context"]["key"], "context.key"),
        ):
            shutil.copy2(original, secure / target)
            (secure / target).chmod(0o444)
        for original, target in (
            (ca, "ca.pem"),
            (peers["worker-0"]["cert"], "worker.pem"),
            (peers["worker-0"]["key"], "worker.key"),
        ):
            shutil.copy2(original, private / target)
            (private / target).chmod(0o444)
        control_net, worker_net = name + "-control", name + "-worker"
        for network, internal in ((control_net, False), (worker_net, True)):
            command(
                "docker",
                "network",
                "create",
                *(["--internal"] if internal else []),
                network,
            )
            networks.append(network)
        with socket.socket() as allocation:
            allocation.bind(("127.0.0.1", 0))
            port = allocation.getsockname()[1]
        config = dict(
            ca="/credentials/ca.pem",
            certificate="/credentials/context.pem",
            key="/credentials/context.key",
            bind="0.0.0.0",
            port=9443,
            allowed_hosts=[f"localhost:{port}", "context:9443"],
            max_handlers=32,
            context_id="S1",
            state_directory="/state",
            listener_fingerprint=peers["listener"]["pin"],
            subjects={
                "alice": PERMISSIONS,
                "bob": PERMISSIONS,
                "observer": ["execution:read"],
            },
            worker_slots={"slot-case": "inc-" + case, "slot-witness": "inc-witness"},
            approved_sources=catalog,
            worker_credentials=dict(
                profile="single-host-preflight",
                identities={
                    peers["worker-0"]["pin"]: dict(
                        slot="slot-case", incarnation="inc-" + case
                    ),
                    peers["worker-1"]["pin"]: dict(
                        slot="slot-witness", incarnation="inc-witness"
                    ),
                },
            ),
            worker_launch="retained-single-use",
            native_children="admission-only",
            native_controls="run-journal",
            native_commands="owner-terminal-candidate",
            native_prompts="owner-reply-candidate",
        )
        dss = None
        if case == "driver":
            dss, dss_net, ip = start_dss(name, code, image, names, networks)
            config["native_driver"] = dict(
                binding="simulator",
                url=f"http://{ip}:8085",
                tcp=[ip, 4545],
                directory="/state/driver",
                commands=["CMD1"],
                telemetry=["TM.POWER.BUS_VOLTAGE"],
            )
        (secure / "config.json").write_bytes(canonical(config))
        (secure / "config.json").chmod(0o444)
        args = [
            "docker",
            "create",
            "--name",
            authority,
            "--init",
            "--read-only",
            "--network",
            control_net,
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
        for source, destination, readonly in (
            (code, "/v08", True),
            (sources, "/catalog", True),
            (secure, "/credentials", True),
            (state, "/state", False),
        ):
            args += [
                "--mount",
                f"type=bind,src={source},dst={destination}"
                + (",readonly" if readonly else ""),
            ]
        args += [
            "--env",
            "PYTHONPATH=/v08/server/src:/v08/driver_plugin/src:/v08/src",
            "--entrypoint",
            "python",
            image,
            "-m",
            "openbexi_spell_dss.context_server" if dss else "openbexi_spell_server",
            "context",
            "--config",
            "/credentials/config.json",
        ]
        names.append(authority)
        command(*args)
        command(
            "docker", "network", "connect", "--alias", "context", worker_net, authority
        )
        if dss:
            command("docker", "network", "connect", dss_net, authority)
        command("docker", "start", authority)
        route = Route(
            f"https://localhost:{port}",
            peers["context"]["pin"],
            tls_context(ca, peers["listener"]["cert"], peers["listener"]["key"]),
        )

        def controller(method, payload, *, subject="alice", key=None):
            return route.call(
                envelope(
                    "S1",
                    subject,
                    method,
                    payload,
                    key or str(uuid.uuid4())
                    if method not in {"execution.list", "source.catalog"}
                    else None,
                )
            )

        end = time.monotonic() + 20
        while True:
            try:
                controller("execution.list", {})
                break
            except Exception:
                if time.monotonic() > end:
                    raise RuntimeError("Step 1 Context startup failed")
                time.sleep(0.1)
        entries = {
            e["procedure_id"]: e for e in controller("source.catalog", {})["procedures"]
        }
        connection = controller("session.open", {})["connection_id"]

        def reserve(key):
            return controller(
                "execution.reserve",
                dict(
                    procedure_id=key,
                    connection_id=connection,
                    **{
                        k: entries[key][k]
                        for k in (
                            "source_revision",
                            "source_sha256",
                            "runtime_image",
                            "driver_binding",
                        )
                    },
                ),
            )

        execution = reserve("main")
        reserve("witness")
        proof = dict(
            execution_id=execution["id"],
            connection_id=connection,
            expected_epoch=execution["epoch"],
            connection_generation=execution["connection_generation"],
            capability=execution["capability"],
        )
        params = dict(
            ca=str(ca),
            certificate=str(peers["worker-0"]["cert"]),
            key=str(peers["worker-0"]["key"]),
            context_url=f"https://localhost:{port}",
            context_fingerprint=peers["context"]["pin"],
            context_id="S1",
            execution_id=execution["id"],
            worker_slot="slot-case",
            worker_incarnation="inc-" + case,
            snapshot_directory=str(snapshot),
        )
        preflight(params)
        grant = controller("execution.start", proof)["grant"]
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
                    native_prompt_gate=True,
                    native_terminal_gate=True,
                    native_step1_probe=case,
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
            worker_net,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            "1536m",
            "--user",
            "10003:10003",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m",
            "--tmpfs",
            "/workspace:rw,nosuid,nodev,size=16m,mode=0700,uid=10003,gid=10003",
        ]
        for source, destination in (
            (code, "/v08"),
            (snapshot, "/source"),
            (private, "/credentials"),
            (control, "/control"),
        ):
            args += ["--mount", f"type=bind,src={source},dst={destination},readonly"]
        args += [
            "--entrypoint",
            "python",
            image,
            "-I",
            "/v08/agent.py",
            "--config",
            "/credentials/config.json",
        ]
        names.append(name)
        command(*args)
        await_event([name], "native-ready", seconds=45)
        original_pids = process_inventory(name)
        report["initial_processes"] = original_pids
        root_member = sql(
            state,
            "SELECT instance_id FROM native_members WHERE execution_id=? AND target_id=''",
            (execution["id"],),
        )[0]["instance_id"]
        (control / "start").touch()
        await_event([name], "step1-owner-ready", seconds=10)

        def enqueue(cmd, target=None):
            return controller(
                "execution.command",
                dict(**proof, command=cmd, target_admission_id=target),
            )

        # Negative owner/capability cases happen before the first native effect.
        bad = dict(
            proof, capability="0" * 64, command="CMD_ABORT", target_admission_id=None
        )
        try:
            controller("execution.command", bad)
        except Fault as error:
            if error.status != 403:
                raise
        else:
            raise RuntimeError("Forged owner capability admitted a terminal operation")
        enqueue("CMD_RUN")
        wait(name, lambda: marker(name, "body-entered"), "native procedure body")
        expected = "FINISHED"
        if case in {
            "answer",
            "cancel",
            "abort-prompt",
            "duplicate-prompt",
            "late-prompt",
            "timeout-answer",
            "timeout-cancel",
        }:
            pending = wait(
                name,
                lambda: sql(
                    state,
                    "SELECT * FROM native_prompts WHERE execution_id=? AND state='OPEN'",
                    (execution["id"],),
                ),
                "real native prompt",
            )[0]

            def respond(prompt, action="ANSWER", answer="Y"):
                return controller(
                    "execution.prompt.reply",
                    dict(
                        **proof,
                        prompt_id=prompt["prompt_id"],
                        target_admission_id=prompt["target_id"] or None,
                        definition_sha256=prompt["definition_hash"],
                        action=action,
                        answer=answer,
                    ),
                )

            if case == "abort-prompt":
                enqueue("CMD_ABORT")
                expected = "ABORTED"
            else:
                if case == "answer":
                    (control / "inject-unowned").touch()
                    await_event([name], "step1-unowned-prompt-dispatched", seconds=5)
                    time.sleep(0.15)
                    if marker(name, "answered"):
                        raise RuntimeError(
                            "Unowned original native reply selected an answer"
                        )
                respond(
                    pending,
                    "CANCEL" if case in {"cancel", "timeout-cancel"} else "ANSWER",
                    None
                    if case in {"cancel", "timeout-cancel"}
                    else "operator"
                    if case == "timeout-answer"
                    else "Y",
                )
                if case == "cancel":
                    expected = "ABORTED"
                if case in {"timeout-answer", "timeout-cancel"}:
                    # Real original native timer must select its default while
                    # a separately authenticated response is waiting.
                    await_event([name], "step1-prompt-consumption-waiting", seconds=5)
                    wait(
                        name,
                        lambda: marker(name, "timed-out"),
                        "native timeout selected default",
                        seconds=8,
                    )
                    (control / "finish").touch()
                if case == "late-prompt":
                    second = wait(
                        name,
                        lambda: sql(
                            state,
                            "SELECT * FROM native_prompts WHERE execution_id=? AND state='OPEN' AND prompt_id!=?",
                            (execution["id"], pending["prompt_id"]),
                        ),
                        "second native prompt",
                    )[0]
                    (control / "replay-prompt").touch()
                    await_event([name], "step1-original-prompt-replayed", seconds=5)
                    time.sleep(0.15)
                    if marker(name, "answered"):
                        raise RuntimeError(
                            "Prior-generation prompt reply answered the new generation"
                        )
                    respond(second)
                if case in {"answer", "duplicate-prompt", "late-prompt"}:
                    wait(
                        name, lambda: marker(name, "answered"), "explicit native answer"
                    )
                    if case == "duplicate-prompt":
                        (control / "replay-prompt").touch()
                        await_event([name], "step1-original-prompt-replayed", seconds=5)
                        time.sleep(0.1)
                    (control / "finish").touch()
        elif case == "timeout":
            wait(name, lambda: marker(name, "timed-out"), "native timeout/default")
            (control / "finish").touch()
        elif case == "failure":
            expected = "ERROR"
        elif case in {"abort-running", "close-running", "family", "driver"}:
            if case == "driver":
                wait(
                    name,
                    lambda: marker(name, "driver-sent"),
                    "original native driver effect",
                )
            if case == "family":
                wait(
                    name,
                    lambda: marker(name, "child-running"),
                    "admitted native child running",
                )
                child_members = sql(
                    state,
                    "SELECT * FROM native_members WHERE execution_id=? AND target_id!=''",
                    (execution["id"],),
                )
                if len(child_members) != 1:
                    raise RuntimeError("Unexpected native child inventory")
                original_pids = process_inventory(name)
                report["expanded_processes"] = original_pids
            if case == "close-running":
                attempted = enqueue("CMD_CLOSE")
                wait(
                    name,
                    lambda: sql(
                        state,
                        "SELECT 1 FROM native_owner_commands WHERE command_id=? AND state='FORWARD_UNPROVEN'",
                        (attempted["command_id"],),
                    ),
                    "running CLOSE forwarded",
                )
                time.sleep(0.25)
                if sql(
                    state,
                    "SELECT * FROM native_terminal_intents WHERE command_id=?",
                    (attempted["command_id"],),
                ):
                    raise RuntimeError("Running CLOSE acquired terminal permission")
                if native_status(name, root_member) != "RUNNING":
                    raise RuntimeError("Denied CLOSE changed native state")
            enqueue("CMD_ABORT")
            expected = "ABORTED"
            if case == "family":
                for child_member in child_members:
                    enqueue("CMD_ABORT", child_member["target_id"])
                    wait(
                        name,
                        lambda: native_status(name, child_member["instance_id"])
                        == "ABORTED",
                        "native child abort",
                    )
                    enqueue("CMD_CLOSE", child_member["target_id"])
        elif case == "forced-loss":
            # Independent HOST fault injection, never an owner command or a
            # substitute for positive native ABORT/CLOSE. Uncertainty is retained.
            command("docker", "kill", "--signal", "KILL", name)
            report["injected_worker_loss"] = True
            report["terminal_outcome"] = "UNKNOWN"
        if case != "forced-loss":
            wait(
                name,
                lambda: native_status(name, root_member) == expected,
                "native terminal " + expected,
                seconds=20,
            )
            if case in {"cancel", "abort-prompt"} and marker(
                name, "unsafe-after-cancel"
            ):
                raise RuntimeError(
                    "Native cancellation executed the forbidden continuation"
                )
            if expected in {"ERROR", "ABORTED"}:
                wait(
                    name,
                    lambda: marker(name, "unwound"),
                    "original native exception/finally unwind",
                )
            wait(
                name,
                lambda: not sql(
                    state,
                    "SELECT 1 FROM native_prompts WHERE execution_id=? AND state='OPEN'",
                    (execution["id"],),
                ),
                "native prompt outcome closure",
            )
            close = enqueue("CMD_CLOSE")
            await_event([name], "step1-native-family-exited", seconds=20)
            report["terminal_outcome"] = expected
            report["native_close_command_id"] = close["command_id"]
        wait(
            name,
            lambda: not json.loads(command("docker", "inspect", name))[0]["State"][
                "Running"
            ],
            "single-use worker exit",
            seconds=15,
            allow_exit=True,
        )
        info = json.loads(command("docker", "inspect", name))[0]
        if info["State"]["Pid"] != 0 or info["State"]["OOMKilled"]:
            raise RuntimeError(
                "Worker termination or bounded memory accounting differs"
            )
        if case != "forced-loss" and info["State"]["ExitCode"] != 0:
            raise RuntimeError("Native worker ended unsuccessfully")
        wait(
            name,
            lambda: all_gone(original_pids),
            "independent host process absence",
            seconds=10,
            allow_exit=True,
        )
        reservations = sql(state, "SELECT COUNT(*) AS n FROM reservations")[0]["n"]
        spent = sql(state, "SELECT SUM(spent) AS n FROM workers")[0]["n"]
        if reservations != (3 if case == "family" else 2) or spent != 1:
            raise RuntimeError(
                "Terminal cleanup changed holds or single-use worker state"
            )
        if case != "forced-loss":
            # Old owner cannot resurrect a terminal runtime with a fresh RUN ID.
            try:
                enqueue("CMD_RUN")
            except Fault as error:
                if error.status != 403:
                    raise
            else:
                raise RuntimeError("A terminal runtime accepted another owner RUN")
        if dss:
            first = dss_state(dss)["core"]["commands_executed"]
            time.sleep(0.5)
            second = dss_state(dss)["core"]["commands_executed"]
            if first != 1 or second != 1:
                raise RuntimeError("Independent DSS effect count differs after cleanup")
            effect_rows = sql(
                state, "SELECT stage,state,receipt_hash FROM effect_intents"
            )
            if {r["stage"] for r in effect_rows} != {
                "TRANSPORT",
                "LOADING",
                "RELEASE",
                "ACKNOWLEDGEMENT",
                "ONBOARD_EXECUTION",
            } or any(
                r["state"] != "ACKED" or not r["receipt_hash"] for r in effect_rows
            ):
                raise RuntimeError(
                    "Actual native driver effect receipts are incomplete"
                )
            report["driver_effects"] = dict(
                dss_commands=1,
                all_five_stages_acked=True,
                count_stable_after_cleanup=True,
            )
        report.update(
            passed=True,
            processes_absent=True,
            container_stopped=True,
            retained_reservations=reservations,
            spent_workers=spent,
            commands=sql(
                state,
                "SELECT command,state,diagnostic FROM native_owner_commands ORDER BY sequence",
            ),
            terminal_intents=sql(
                state,
                "SELECT command,native_status,prompt_id FROM native_terminal_intents",
            ),
            prompts=sql(state, "SELECT state,outcome FROM native_prompts"),
            lifecycle_events=sql(
                state, "SELECT COUNT(*) AS n FROM native_driver_events"
            )[0]["n"],
        )
    except Exception as error:
        report["error"] = dict(type=type(error).__name__, message=str(error)[:512])
    finally:
        if name in names:
            try:
                report["worker_events"] = events(name)
            except Exception:
                report["worker_log_unavailable"] = True
        if authority in names:
            try:
                # Authority logs are protocol diagnostics only; no request bodies.
                report["context_tail"] = command("docker", "logs", authority)[-12000:]
            except Exception:
                pass
        # Host-owned cleanup is not relabeled as positive native completion.
        for container in reversed(names):
            try:
                command("docker", "rm", "-f", container, timeout=20)
            except Exception:
                report["host_cleanup_failed"] = True
                report["passed"] = False
        for network in reversed(networks):
            try:
                command("docker", "network", "rm", network, timeout=20)
            except Exception:
                report["host_cleanup_failed"] = True
                report["passed"] = False
        write_json(output / (case + ".json"), report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / ".qualification/v08-step1-native" / (
        "run-" + uuid.uuid4().hex
    )
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="openbexi.step1-native-cohort/1",
        passed=False,
        plugin_commit=command("git", "rev-parse", "HEAD"),
        ide_commit=json.loads((ROOT / "docs/v0.8/IDE_PAIR.json").read_text())[
            "ide_commit"
        ],
        frozen_image=IMAGE,
        frozen_archive_sha256=ARCHIVE_SHA256,
        source_sha256={},
        cases=[],
        step1_qualified=False,
        ownership_transfer_enabled=False,
    )
    inputs = (
        list((ROOT / "host_runtime").rglob("*.py"))
        + list((ROOT / "host_runtime/native").glob("*.H"))
        + list((ROOT / "server/src").rglob("*.py"))
        + list((ROOT / "driver_plugin/src").rglob("*.py"))
        + [Path(__file__), ROOT / "scripts/qualify_v08_native_launch.py"]
    )
    report["source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in inputs
    }
    try:
        if os.getuid() == 0:
            raise RuntimeError("Qualification requires an unprivileged host operator")
        with tempfile.TemporaryDirectory(prefix="v08-full-step1-") as temporary:
            temporary = Path(temporary)
            prefix = "v08-step1-" + uuid.uuid4().hex[:8]
            image, build = build_native(temporary, output, prefix)
            report["native_image"] = image
            report["native_build"] = build
            code = code_mount(temporary)
            ca, peers = pki(temporary / "pki")
            for case in args.cases:
                value = run_case(
                    case, temporary, output, prefix, code, image, ca, peers
                )
                report["cases"].append(
                    dict(case=case, passed=value["passed"], error=value.get("error"))
                )
                print(json.dumps(report["cases"][-1]), flush=True)
            report["passed"] = all(r["passed"] for r in report["cases"])
    except Exception as error:
        report["error"] = dict(type=type(error).__name__, message=str(error)[:512])
    write_json(output / "result.json", report)
    print(
        json.dumps(
            dict(passed=report["passed"], output=str(output), step1_qualified=False)
        ),
        flush=True,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
