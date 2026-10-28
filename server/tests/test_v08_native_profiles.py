"""Explicit build settings, long-soak evidence and original-family cycle tests."""

import json
import importlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host_runtime"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "server/src"))
builder = importlib.import_module("build_native_profile")
cli = importlib.import_module("build_v08_native_profile")
endurance = importlib.import_module("v08_endurance")
cohort = importlib.import_module("v08_handoff_cohort")
Fault = importlib.import_module("openbexi_spell_server.contracts").Fault


def test_failure_observation_identifies_a_real_original_pidfd_without_claiming_oom():
    children = []
    handles = {}
    try:
        for _ in range(8):
            child = subprocess.Popen([sys.executable, "-c", "import signal;signal.pause()"])
            children.append(child)
            handles[child.pid] = os.pidfd_open(child.pid)
        original = {
            "Id": "test-container",
            "State": {"Pid": children[0].pid},
            "Config": {"Env": ["TEST_SECRET=must_not_be_recorded"]},
        }
        before = endurance.process_failure_observation(handles, original)
        assert before["observed_processes"] == before["expected_processes"] == 8
        assert not any(row["pidfd_exited"] for row in before["processes"])
        children[3].terminate()
        children[3].wait(timeout=5)
        after = endurance.process_failure_observation(handles, original)
        assert [row["host_pid"] for row in after["processes"] if row["pidfd_exited"]] == [
            children[3].pid
        ]
        assert after["observation_start_ns"] <= after["observation_end_ns"]
        assert not after["kernel_victim_pid_observed"] and not after["oom_cause_inferred"]
        assert "TEST_SECRET" not in json.dumps(after)
    finally:
        for fd in handles.values():
            os.close(fd)
        for child in children:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)


def test_failure_observation_error_preserves_the_original_endurance_failure(tmp_path, monkeypatch):
    calls = []

    def counters(*_):
        calls.append(True)
        if len(calls) == 1:
            return {"root": 1, "child": 1, "thread": 1}
        raise RuntimeError("original_failure_must_survive")

    def observation(*_, **__):
        raise OSError("injected evidence failure")

    monkeypatch.setattr(cohort, "counters", counters)
    monkeypatch.setattr(endurance, "process_failure_observation", observation)
    monkeypatch.setattr(endurance.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="original_failure_must_survive"):
        endurance.run_soak(
            duration=3600,
            name="container",
            controller=None,
            proof={"connection_id": "test"},
            bob_connection="bob",
            handoff_call=None,
            command=None,
            control=None,
            handles={},
            original={},
            output=tmp_path,
            await_event=None,
        )
    summary = json.loads((tmp_path / "endurance-cycles.json").read_text())
    assert summary["failure"] == "RuntimeError" and summary["passed"] is False
    assert summary["process_failure_observation_error"] == "OSError"


def test_kernel_observation_rejects_unrelated_old_and_malformed_kill_records():
    line = "[   10.125000] Memory cgroup out of memory: Killed process 1234 (SPELL-Context) total-vm:999kB, anon-rss:100kB, file-rss:20kB, shmem-rss:2kB, UID:10003 pgtables:8kB oom_score_adj:0"
    rows = endurance.kernel_oom_observations(line, {1234}, 10 * 10**9, 11 * 10**9)
    assert len(rows) == 1 and rows[0]["host_pid"] == 1234
    assert rows[0]["anonymous_rss_bytes"] == 102400
    assert rows[0]["kernel_boot_ns"] == 10125000000
    assert not endurance.kernel_oom_observations(line, {5678}, 0, 11 * 10**9)
    assert not endurance.kernel_oom_observations(line, {1234}, 11 * 10**9, 12 * 10**9)
    assert not endurance.kernel_oom_observations(line, {1234}, 0, 10 * 10**9)
    assert not endurance.kernel_oom_observations(line + " SECRET=untrusted", {1234}, 0, 11 * 10**9)


def test_controlled_pair_changes_sanitizers_not_optimization():
    sanitized, slink = builder.profile_flags("asan-o2")
    optimized, olink = builder.profile_flags("optimized")
    assert "-O2" in sanitized and "-O2" in optimized
    assert slink == ["-fsanitize=address,undefined"] and olink == []
    assert "-DOPENBEXI_NATIVE_NO_SANITIZERS=1" in optimized
    assert "-DOPENBEXI_NATIVE_NO_SANITIZERS=1" not in sanitized
    assert "-O1" in builder.profile_flags("asan-o1")[0]


def test_unknown_profile_fails_closed():
    with pytest.raises(ValueError):
        builder.profile_flags("release")


@pytest.mark.parametrize(
    "name", ["latest", "python:3.13", "sha256:" + "f" * 63, "x@sha256:" + "X" * 64, "x;sh"]
)
def test_offline_toolchain_refuses_mutable_or_malformed_images(name):
    with pytest.raises(ValueError):
        cli.validate_image(name)


@pytest.mark.parametrize(
    "name", ["sha256:" + "0" * 64, "ghcr.io/arcazj/toolchain@sha256:" + "a" * 64]
)
def test_offline_toolchain_accepts_digest_pins(name):
    assert cli.validate_image(name) == name


def test_latency_percentiles_are_reported_not_certified():
    assert not endurance.latency_summary([])["available"]
    summary = endurance.latency_summary([1, 3, 2, 4])
    assert summary["p50_ms"] == 2.5
    assert summary["p99_ms"] <= summary["maximum_ms"] == 4


class Clock:
    now = 0.0

    def monotonic(self):
        return self.now

    def monotonic_ns(self):
        return int(self.now * 10**9)

    def sleep(self, seconds):
        self.now += seconds


class Rig:
    def __init__(self, clock):
        self.clock = clock
        self.owner, self.epoch, self.generation = "alice", 3, 4
        self.state = "OWNED"
        self.capability = "secret-4"
        self.paused = False
        self.connections = {"alice": "a4", "bob": "b1"}
        self.rotation = 3
        self.denials = 0

    def proof(self):
        return dict(
            execution_id="exec",
            connection_id=self.connections[self.owner],
            expected_epoch=self.epoch,
            connection_generation=self.generation,
            capability=self.capability,
            target_admission_id=None,
        )

    def valid(self, proof):
        return all(proof.get(k) == v for k, v in self.proof().items() if k != "target_admission_id")

    def __call__(self, operation, params, subject="alice"):
        if operation == "execution.list":
            return {
                "executions": [
                    dict(
                        id="exec",
                        owner=self.owner,
                        epoch=self.epoch,
                        control_state=self.state,
                        connection_generation=self.generation,
                        pause_barrier={"quiescence_proven": False},
                    )
                ]
            }
        if operation == "session.open":
            self.connections[subject] = subject + str(self.generation + 1)
            return {"connection_id": self.connections[subject]}
        if operation == "execution.claim":
            self.recipient = subject
            return {"claim_id": "claim"}
        if operation == "execution.decide":
            assert self.valid(params)
            self.pending_owner = self.recipient
            self.pending_epoch = self.epoch + 1
            return {"barrier_id": "barrier"}
        if operation == "execution.rebind":
            if self.state == "CONTROLLER_DISCONNECTED":
                self.pending_owner = self.owner
                self.pending_epoch = self.epoch
                return {"rebind_pending": True, "barrier_id": "barrier"}
            return {"connection_generation": self.generation, "capability": self.capability}
        if operation == "execution.command":
            if (
                not self.valid(params)
                or subject != self.owner
                or self.state == "CONTROLLER_DISCONNECTED"
            ):
                self.denials += 1
                raise Fault(403, "denied")
            return {"command_id": "run"}
        raise AssertionError(operation)

    def lose(self, connection):
        self.state = "CONTROLLER_DISCONNECTED"
        return {"lease_seconds": 1}

    def host(self, operation, **kwargs):
        if operation == "status":
            return {}
        if operation == "complete":
            self.owner, self.epoch = self.pending_owner, self.pending_epoch
            self.generation += 1
            self.capability = "secret-" + str(self.generation)
            self.state = "HANDOFF_PAUSED"
            return {"quiescence_proven": True}
        if operation == "resume":
            self.state = "OWNED"
            self.rotation += 1
            return {"runtime_epoch": "private-epoch-" + str(self.rotation)}
        raise AssertionError(operation)

    def command(self, *args):
        if args == ("docker", "pause", "native"):
            self.paused = True
            self.frozen_counter = int(self.clock.now * 100)
        elif args == ("docker", "unpause", "native"):
            self.paused = False
        else:
            raise AssertionError(args)

    def counters(self, *_):
        value = self.frozen_counter if self.paused else int(self.clock.now * 100)
        return {key: value for key in ("root", "background", "child")}


def test_full_hour_protocol_with_injected_clock_and_host(monkeypatch, tmp_path):
    clock = Clock()
    rig = Rig(clock)
    monkeypatch.setattr(endurance, "time", clock)
    monkeypatch.setattr(endurance, "select", SimpleNamespace(select=lambda *args: ([], [], [])))
    monkeypatch.setattr(cohort, "counters", rig.counters)
    monkeypatch.setattr(cohort, "drain_agent_before_freeze", lambda *args, **kw: None)
    monkeypatch.setattr(cohort, "frozen_evidence", lambda *args, **kw: {"original_processes": 8})
    result = endurance.run_soak(
        duration=3600,
        name="native",
        controller=rig,
        proof=rig.proof(),
        bob_connection="b1",
        handoff_call=rig.host,
        command=rig.command,
        control=tmp_path,
        handles={n: n for n in range(8)},
        original={},
        output=tmp_path,
        await_event=lambda *args, **kw: None,
    )
    assert result["end_ns"] - result["start_ns"] >= 3600 * 10**9
    assert result["extra_transfers"] == 4 and result["extra_reconnections"] == 1
    assert result["final_epoch"] == 7 and rig.rotation == 8
    assert rig.denials == 11
    receipt = (tmp_path / "endurance-cycles.json").read_text()
    assert "secret-" not in receipt and "private-epoch-" not in receipt
    assert json.loads(receipt)["passed"]
    assert (
        not json.loads(receipt)["latency_slo_qualified"]
        if "latency_slo_qualified" in json.loads(receipt)
        else True
    )


def test_endurance_refuses_shortened_duration():
    with pytest.raises(ValueError, match="3600"):
        endurance.run_soak(
            duration=30,
            name=None,
            controller=None,
            proof=None,
            bob_connection=None,
            handoff_call=None,
            command=None,
            control=None,
            handles=None,
            original=None,
            output=None,
            await_event=None,
        )


def test_hour_overlay_preserves_mandatory_source_and_rotation_cap(tmp_path):
    import shutil
    import v08_memory_experiment as experiment

    for relative in experiment.PREIMAGES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    before = (ROOT / "scripts/v08_handoff_cohort.py").read_bytes()
    changes = experiment.prepare_overlay(tmp_path, "optimized-noswap", 3600)
    generated = (tmp_path / "scripts/v08_handoff_cohort.py").read_text()
    compile(generated, "endurance-cohort", "exec")
    assert "run_soak(duration=3600" in generated
    assert "proof_sink=endurance_proof" in generated
    assert "endurance_proof.clear()" in generated
    assert "extra_history_entries" in generated
    assert (ROOT / "scripts/v08_handoff_cohort.py").read_bytes() == before
    assert "host_runtime/python/handoff_runtime.py" not in changes
    assert "self.rotations >= 8" in (ROOT / "host_runtime/python/handoff_runtime.py").read_text()


def test_hour_assessor_requires_cycles_and_records_late_growth(tmp_path):
    import v08_memory_experiment as experiment
    import test_v08_memory_experiment as fixture

    rows = fixture.evidence(tmp_path, "optimized-noswap", seconds=3600)
    failed = experiment.assess_experiment(tmp_path, "optimized-noswap", 3600)
    assert not failed["passed"]
    receipt = {
        "passed": True,
        "extra_transfers": 4,
        "extra_reconnections": 1,
        "rotations": 8,
        "rpc_latency": {"available": True, "samples": 20, "p99_ms": 7},
    }
    (tmp_path / "endurance-cycles.json").write_text(json.dumps(receipt))
    result = experiment.assess_experiment(tmp_path, "optimized-noswap", 3600)
    assert result["passed"] and result["endurance_cycles_verified"]
    assert result["late_ten_minute_growth_bytes"] == 0
    assert not result["full_v08_qualified"]
    assert not result["allocator_observations_available"]
    receipt["extra_reconnections"] = 0
    (tmp_path / "endurance-cycles.json").write_text(json.dumps(receipt))
    assert not experiment.assess_experiment(tmp_path, "optimized-noswap", 3600)["passed"]
    assert len(rows) > 1800
