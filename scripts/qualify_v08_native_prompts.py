"""Actual source-derived native prompt cohort, never whole-lifecycle approval.

Uses the production candidate JSON/Unix socket wrapper, pinned process identities,
real SPELL Context/Executor/scheduler and mTLS authority. Fixed sources only.
"""

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import uuid

from qualify_v08_native_launch import (
    IMAGE,
    PERMISSIONS,
    ROOT,
    command,
    events,
    load_runtime,
    pki,
)
from openbexi_spell_server.contracts import Fault, canonical, envelope
from openbexi_spell_server.transport import Route, tls_context
from openbexi_spell_server.worker import preflight

INTRO = (
    "from pathlib import Path\nimport time\n"
    "from spell.lang.functions import Prompt\nfrom spell.lang.constants import LIST\n"
)
PROMPT = "Prompt({title!r}, ['YES :Yes','NO :No'], Type=LIST, Default='NO', Timeout={timeout}, HandleError=False)"


def fixture_sources():
    sources = {}
    for case in ("answer", "cancel", "timeout", "late", "failure", "sequential"):
        timeout = 0.35 if case in ("timeout", "late") else 25
        code = (
            INTRO
            + "began=time.monotonic()\nanswer="
            + PROMPT.format(title=case, timeout=timeout)
            + "\n"
        )
        if case == "cancel":
            code += "Path('/workspace/prompt-after-cancel').write_text('UNSAFE')\n"
        elif case == "failure":
            code += "assert answer=='YES'\nraise RuntimeError('EXPECTED_PROMPT_COHORT_FAILURE')\n"
        else:
            expected = "NO" if case in ("timeout", "late") else "YES"
            code += f"assert answer=={expected!r}, repr(answer)\n"
            if case in ("timeout", "late"):
                code += "assert time.monotonic()-began>=0.35\n"
            if case == "sequential":
                code += (
                    "second="
                    + PROMPT.format(title="second", timeout=25)
                    + "\nassert second=='NO', repr(second)\n"
                )
            code += f"Path('/workspace/prompt-result.json').write_text({json.dumps(json.dumps({'case': case, 'passed': True}))})\n"
        sources[case + ".py"] = code
    sources["child.py"] = (
        "from pathlib import Path\nfrom spell.lang.functions import StartProc\n"
        "assert StartProc('prompt_child_body',Automatic=True,Visible=True,Blocking=True,HandleError=False) is True\n"
        "assert Path('/workspace/prompt-child-completed').read_text()=='YES'\n"
        'Path(\'/workspace/prompt-result.json\').write_text(\'{"case":"child","passed":true}\')\n'
    )
    sources["prompt_child_body.py"] = (
        INTRO
        + "answer="
        + PROMPT.format(title="child", timeout=25)
        + (
            "\nassert answer=='YES'\nPath('/workspace/prompt-child-completed').write_text(answer)\n"
        )
    )
    return sources


def wait_for(test, message, *, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = test()
        if result:
            return result
        time.sleep(0.05)
    raise TimeoutError(message)


def rows(database, statement, args=()):
    with closing(sqlite3.connect("file:" + str(database) + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(statement, args)]


def native_identities(name):
    records = []
    for line in command("docker", "top", name, "-eo", "pid,comm").splitlines()[1:]:
        pid, executable = line.split(maxsplit=1)
        if executable.startswith("SPELL-"):
            raw = Path("/proc") / pid / "stat"
            records.append(
                dict(
                    pid=int(pid),
                    start=raw.read_text().rsplit(")", 1)[1].split()[19],
                    executable=executable,
                )
            )
    return records


def identity_gone(record):
    try:
        stat = (
            (Path("/proc") / str(record["pid"]) / "stat")
            .read_text()
            .rsplit(")", 1)[1]
            .split()
        )
    except FileNotFoundError:
        return True
    return stat[19] != record["start"]


def main():
    output = ROOT / ".qualification/v08-native-prompts" / ("run-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    report = dict(
        schema="openbexi.native-prompt-cohort/1",
        passed=False,
        git_head=command("git", "rev-parse", "HEAD"),
        cases=[],
        full_step1_qualified=False,
        full_v08_qualified=False,
        effective_transfer=False,
        cleanup_scope="single-use-container-termination-only",
    )
    relevant = [
        p
        for sub in ("server/src", "host_runtime", "scripts")
        for p in (ROOT / sub).rglob("*")
        if p.is_file() and p.suffix in (".py", ".H", ".cpp")
    ]
    report["source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in relevant
    }
    names = []
    networks = []
    prefix = "v08-prompt-" + uuid.uuid4().hex[:12]
    try:
        if os.getuid() == 0:
            raise RuntimeError("Hosted qualification requires non-root host operator")
        with tempfile.TemporaryDirectory(prefix=prefix) as temp:
            temp = Path(temp)
            try:
                load_runtime(temp, output)
                ca, peers = pki(temp / "pki")
                code = temp / "code"
                package = code / "server/src/openbexi_spell_server"
                package.mkdir(parents=True)
                for p in (ROOT / "server/src/openbexi_spell_server").glob("*.py"):
                    shutil.copy2(p, package / p.name)
                for src, dst in [
                    ("v08_worker.py", "agent.py"),
                    ("native.py", "native_candidate.py"),
                    ("children.py", "children.py"),
                    ("child_gate.py", "child_gate.py"),
                    ("control_journal.py", "control_journal.py"),
                    ("prompt_replies.py", "prompt_replies.py"),
                ]:
                    shutil.copy2(ROOT / "host_runtime/python" / src, code / dst)
                build = temp / "build"
                build.mkdir()
                for p in (ROOT / "host_runtime/native").glob("*.H"):
                    shutil.copy2(p, build / p.name)
                shutil.copy2(
                    ROOT / "host_runtime/build_admission_context.py", build / "build.py"
                )
                shutil.copy2(
                    ROOT / "host_runtime/native_prompt_patch.py",
                    build / "native_prompt_patch.py",
                )
                base = prefix + "-base"
                image = prefix + "-image"
                command("docker", "tag", IMAGE, base)
                (build / "Dockerfile").write_text(
                    "FROM " + base + "\nUSER root\n"
                    "RUN apt-get update && apt-get install -y --no-install-recommends git g++ nlohmann-json3-dev libxerces-c-dev liblog4cplus-dev libncurses-dev zlib1g-dev\n"
                    "COPY *.H build.py native_prompt_patch.py /candidate/\n"
                    "RUN python /candidate/build.py --native-prompts\nUSER 10003:10003\n"
                )
                compiled = subprocess.run(
                    ["docker", "build", "-t", image, str(build)],
                    capture_output=True,
                    timeout=900,
                )
                (output / "native-build.log").write_bytes(
                    compiled.stdout + compiled.stderr
                )
                if compiled.returncode:
                    raise RuntimeError(
                        "Full source-derived prompt-enabled native build failed"
                    )
                image = command(
                    "docker", "image", "inspect", "--format", "{{.Id}}", image
                )
                report["image"] = image
                report["native_build"] = json.loads(
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
                if report["native_build"].get("native_prompt_hooks") is not True:
                    raise RuntimeError("Built image lacks actual native prompt hooks")
                sources = temp / "sources"
                snapshot = temp / "snapshot"
                sources.mkdir()
                snapshot.mkdir()
                for filename, content in fixture_sources().items():
                    (sources / filename).write_text(content)
                    (snapshot / filename).write_text(content)
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
                    "fixed native prompt qualification sources",
                )
                revision = command("git", "-C", sources, "rev-parse", "HEAD")
                case_names = [
                    "answer",
                    "timeout",
                    "late",
                    "sequential",
                    "child",
                    "cancel",
                    "failure",
                ]
                slots = {
                    "slot-" + str(i): "incarnation-" + str(i)
                    for i in range(len(case_names))
                }
                catalog = {
                    case: dict(
                        repository="/catalog",
                        revision=revision,
                        entrypoint=case + ".py",
                        runtime_image=image,
                        driver_binding="context-audit",
                        aliases=[],
                    )
                    for case in case_names
                }
                catalog["prompt-child-body"] = dict(
                    catalog["child"], entrypoint="prompt_child_body.py"
                )
                state = temp / "state"
                state.mkdir(mode=0o700)
                database = state / "context.sqlite3"
                secure = temp / "context-credentials"
                secure.mkdir()
                for original, target in [
                    (ca, "ca.pem"),
                    (peers["context"]["cert"], "context.pem"),
                    (peers["context"]["key"], "context.key"),
                ]:
                    shutil.copy2(original, secure / target)
                    (secure / target).chmod(0o444)
                with socket.socket() as s:
                    s.bind(("127.0.0.1", 0))
                    port = s.getsockname()[1]
                config = dict(
                    ca="/credentials/ca.pem",
                    certificate="/credentials/context.pem",
                    key="/credentials/context.key",
                    bind="0.0.0.0",
                    port=9443,
                    allowed_hosts=[f"localhost:{port}", "context:9443"],
                    max_handlers=32,
                    context_id="PROMPTS",
                    state_directory="/state",
                    listener_fingerprint=peers["listener"]["pin"],
                    subjects={"alice": PERMISSIONS, "bob": PERMISSIONS},
                    worker_slots=slots,
                    approved_sources=catalog,
                    worker_credentials=dict(
                        profile="single-host-preflight",
                        identities={
                            peers["worker-" + str(i)]["pin"]: dict(
                                slot="slot-" + str(i),
                                incarnation="incarnation-" + str(i),
                            )
                            for i in range(len(case_names))
                        },
                    ),
                    worker_launch="retained-single-use",
                    native_children="admission-only",
                    native_controls="run-journal",
                    native_prompts="owner-reply-candidate",
                )
                (secure / "config.json").write_bytes(canonical(config))
                network = prefix + "-control"
                command("docker", "network", "create", network)
                networks.append(network)
                context = prefix + "-context"
                names.append(context)
                args = [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    context,
                    "--init",
                    "--read-only",
                    "--network",
                    network,
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
                for src, dst, read in [
                    (code, "/v08", True),
                    (sources, "/catalog", True),
                    (secure, "/credentials", True),
                    (state, "/state", False),
                ]:
                    args += [
                        "--mount",
                        f"type=bind,src={src},dst={dst}"
                        + (",readonly" if read else ""),
                    ]
                args += [
                    "--env",
                    "PYTHONPATH=/v08/server/src",
                    "--entrypoint",
                    "python",
                    image,
                    "-m",
                    "openbexi_spell_server",
                    "context",
                    "--config",
                    "/credentials/config.json",
                ]
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
                            "PROMPTS",
                            subject,
                            method,
                            payload,
                            None
                            if method in ("execution.list", "source.catalog")
                            else str(uuid.uuid4()),
                        )
                    )

                def ready():
                    try:
                        return controller("execution.list", {})
                    except (OSError, Fault):
                        return False

                wait_for(ready, "Context readiness timeout", timeout=25)
                entries = {
                    p["procedure_id"]: p
                    for p in controller("source.catalog", {})["procedures"]
                }
                for index, case in enumerate(case_names):
                    result = dict(case=case, passed=False)
                    report["cases"].append(result)
                    connection = controller("session.open", {})["connection_id"]
                    approved = entries[case]
                    execution = controller(
                        "execution.reserve",
                        dict(
                            procedure_id=case,
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
                    peer = peers["worker-" + str(index)]
                    params = dict(
                        ca=str(ca),
                        certificate=str(peer["cert"]),
                        key=str(peer["key"]),
                        context_url=f"https://localhost:{port}",
                        context_fingerprint=peers["context"]["pin"],
                        context_id="PROMPTS",
                        execution_id=execution["id"],
                        worker_slot="slot-" + str(index),
                        worker_incarnation="incarnation-" + str(index),
                        snapshot_directory=str(snapshot),
                    )
                    preflight(params)
                    proof = dict(
                        execution_id=execution["id"],
                        connection_id=connection,
                        expected_epoch=execution["epoch"],
                        connection_generation=execution["connection_generation"],
                        capability=execution["capability"],
                    )
                    grant = controller("execution.start", proof)["grant"]
                    credentials = temp / ("worker-" + case)
                    credentials.mkdir()
                    for original, target in [
                        (ca, "ca.pem"),
                        (peer["cert"], "worker.pem"),
                        (peer["key"], "worker.key"),
                    ]:
                        shutil.copy2(original, credentials / target)
                        (credentials / target).chmod(0o444)
                    inside = dict(
                        params,
                        ca="/credentials/ca.pem",
                        certificate="/credentials/worker.pem",
                        key="/credentials/worker.key",
                        context_url="https://context:9443",
                        snapshot_directory="/source",
                    )
                    (credentials / "config.json").write_bytes(
                        canonical(
                            dict(
                                preflight=inside,
                                grant=grant,
                                start_barrier="/control/start",
                                native_child_gate=True,
                                native_prompt_gate=True,
                                native_prompt_probe=True,
                            )
                        )
                    )
                    (credentials / "config.json").chmod(0o444)
                    control = temp / ("control-" + case)
                    control.mkdir()
                    worker = prefix + "-" + case
                    net = worker + "-net"
                    command("docker", "network", "create", "--internal", net)
                    networks.append(net)
                    command(
                        "docker",
                        "network",
                        "connect",
                        "--alias",
                        "context",
                        net,
                        context,
                    )
                    args = [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        worker,
                        "--init",
                        "--read-only",
                        "--network",
                        net,
                        "--cap-drop",
                        "ALL",
                        "--security-opt",
                        "no-new-privileges",
                        "--pids-limit",
                        "256",
                        "--memory",
                        "1536m",
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
                    for src, dst in [
                        (snapshot, "/source"),
                        (code, "/v08"),
                        (credentials, "/credentials"),
                        (control, "/control"),
                    ]:
                        args += ["--mount", f"type=bind,src={src},dst={dst},readonly"]
                    args += [
                        "--entrypoint",
                        "python",
                        image,
                        "-I",
                        "/v08/agent.py",
                        "--config",
                        "/credentials/config.json",
                    ]
                    names.append(worker)
                    command(*args)

                    def observed(kind):
                        logs = events(worker)
                        failed = [
                            e for e in logs if e["event"] == "native-worker-failed"
                        ]
                        if failed:
                            raise RuntimeError("Native worker failed before " + kind)
                        return next((e for e in logs if e["event"] == kind), None)

                    wait_for(
                        lambda: observed("native-ready"),
                        "Native startup timeout",
                        timeout=40,
                    )
                    tracked = native_identities(worker)
                    if len(tracked) != 3:
                        raise RuntimeError(
                            "Native Listener/Context/Executor inventory differs"
                        )
                    (control / "start").write_text("single attempt")
                    replies = []
                    known = set()
                    denials = 0
                    until = time.monotonic() + 40
                    while time.monotonic() < until:
                        terminal = observed("native-prompt-terminal-observed")
                        active = rows(
                            database,
                            "SELECT * FROM native_prompts WHERE execution_id=? ORDER BY rowid",
                            (execution["id"],),
                        )
                        for prompt in active:
                            if prompt["prompt_id"] in known:
                                continue
                            if prompt["state"] != "OPEN":
                                if case == "late":
                                    invalid = dict(
                                        proof,
                                        prompt_id=prompt["prompt_id"],
                                        target_admission_id=prompt["target_id"] or None,
                                        definition_sha256=prompt["definition_hash"],
                                        action="ANSWER",
                                        answer="YES",
                                    )
                                    try:
                                        controller("execution.prompt.reply", invalid)
                                    except Fault as e:
                                        if e.status not in (403, 409):
                                            raise
                                        denials += 1
                                    else:
                                        raise RuntimeError(
                                            "Closed native prompt accepted a late reply"
                                        )
                                known.add(prompt["prompt_id"])
                                continue
                            if case in ("timeout", "late"):
                                continue
                            selected = (
                                "NO" if case == "sequential" and replies else "YES"
                            )
                            payload = dict(
                                proof,
                                prompt_id=prompt["prompt_id"],
                                target_admission_id=prompt["target_id"] or None,
                                definition_sha256=prompt["definition_hash"],
                                action="CANCEL" if case == "cancel" else "ANSWER",
                                answer=None if case == "cancel" else selected,
                            )
                            # Same real pending native prompt: wrong owner and wrong digest must fail before admission.
                            for subject, body in [
                                ("bob", payload),
                                ("alice", dict(payload, definition_sha256="0" * 64)),
                            ]:
                                try:
                                    controller("execution.prompt.reply", body, subject)
                                except Fault as e:
                                    if e.status not in (403, 409):
                                        raise
                                    denials += 1
                                else:
                                    raise RuntimeError(
                                        "Invalid native prompt authority was admitted"
                                    )
                            replies.append(
                                controller("execution.prompt.reply", payload)[
                                    "reply_id"
                                ]
                            )
                            known.add(prompt["prompt_id"])
                        if terminal:
                            break
                        time.sleep(0.05)
                    else:
                        raise TimeoutError("Native prompt terminal observation expired")
                    expected = (
                        "ABORTED"
                        if case == "cancel"
                        else "ERROR"
                        if case == "failure"
                        else "FINISHED"
                    )
                    if terminal["native_status"] != expected:
                        raise RuntimeError(
                            "Native terminal status differs: "
                            + str(terminal["native_status"])
                        )
                    final = rows(
                        database,
                        "SELECT state,outcome,target_id FROM native_prompts WHERE execution_id=? ORDER BY rowid",
                        (execution["id"],),
                    )
                    expected_outcome = (
                        "CANCEL_SELECTED"
                        if case == "cancel"
                        else "TIMEOUT"
                        if case in ("timeout", "late")
                        else "ANSWER_SELECTED"
                    )
                    count = 2 if case == "sequential" else 1
                    if len(final) != count or any(
                        r["state"] != "CLOSED" or r["outcome"] != expected_outcome
                        for r in final
                    ):
                        raise RuntimeError("Native prompt durable outcomes differ")
                    if case == "child" and not final[0]["target_id"]:
                        raise RuntimeError("Child prompt incorrectly bound to root")
                    terminal_pids = native_identities(worker)
                    tracked += [r for r in terminal_pids if r not in tracked]
                    if case not in ("cancel", "failure"):
                        marker = json.loads(
                            command(
                                "docker",
                                "exec",
                                worker,
                                "python",
                                "-I",
                                "-c",
                                "from pathlib import Path; print(Path('/workspace/prompt-result.json').read_text())",
                            )
                        )
                        if marker != {"case": case, "passed": True}:
                            raise RuntimeError("Actual native effect marker differs")
                    else:
                        command(
                            "docker",
                            "exec",
                            worker,
                            "python",
                            "-I",
                            "-c",
                            "from pathlib import Path; assert not Path('/workspace/prompt-after-cancel').exists(); assert not Path('/workspace/prompt-result.json').exists()",
                        )
                    (control / "terminal-inspected").write_text(
                        "host observed actual terminal"
                    )
                    exitcode = command("docker", "wait", worker, timeout=25)
                    if exitcode != ("1" if case in ("cancel", "failure") else "0"):
                        raise RuntimeError(
                            "Worker exit does not match expected native outcome"
                        )
                    wait_for(
                        lambda: all(identity_gone(p) for p in tracked),
                        "Original native process remained after container exit",
                        timeout=5,
                    )
                    info = json.loads(command("docker", "inspect", worker))[0]
                    if info["State"]["Running"] or info["State"]["OOMKilled"]:
                        raise RuntimeError("Native cohort OOM or still running")
                    holds = rows(
                        database, "SELECT COUNT(*) AS count FROM reservations"
                    )[0]["count"]
                    if holds != (
                        index + 1 + (1 if index >= case_names.index("child") else 0)
                    ):
                        raise RuntimeError(
                            "Uncertain native holds were incorrectly released"
                        )
                    result.update(
                        passed=True,
                        native_status=expected,
                        prompt_count=count,
                        reply_count=len(replies),
                        authority_denials=denials,
                        prompt_outcome=expected_outcome,
                        original_native_processes_exited=len(tracked),
                        original_worker_exit_code=int(exitcode),
                        holds_retained=holds,
                        native_child=case == "child",
                        full_effect_settlement_proven=False,
                        worker_reuse_authorized=False,
                    )
                    (output / (case + "-events.json")).write_text(
                        json.dumps(events(worker), indent=2) + "\n"
                    )
                    (output / "result.json").write_text(
                        json.dumps(report, indent=2) + "\n"
                    )
                report["passed"] = True
            finally:
                for name in names:
                    try:
                        (output / (name + "-events.json")).write_text(
                            json.dumps(events(name), indent=2) + "\n"
                        )
                    except Exception:
                        pass
                for name in reversed(names):
                    subprocess.run(
                        ["docker", "rm", "-f", name], capture_output=True, timeout=30
                    )
                for network in reversed(networks):
                    subprocess.run(
                        ["docker", "network", "rm", network],
                        capture_output=True,
                        timeout=30,
                    )
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=report["passed"], error=report.get("error"), output=str(output))
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
