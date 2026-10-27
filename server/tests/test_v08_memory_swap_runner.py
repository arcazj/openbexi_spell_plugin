"""Hosted scratch-swap isolation is opt-in, reversible, and evidence-producing.

Transaction tests use a fake host: they do not invoke sudo or alter kernel swap.
"""

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "swap_runner_test", ROOT / "scripts/v08_memory_swap_runner.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ENTRY = dict(path="/mnt/swapfile", kind="file", size_kib=2097148, used_kib=0, priority=-2)
IDENTITY = [1, 2, 2 * runner.GIB, 0, 0o600]


class FakeHost:
    def __init__(self, entries=None, outcome=0, fault=None):
        self.entries = copy.deepcopy(entries or [])
        self.actions = []
        self.outcome = outcome
        self.fault = fault
        self.finished = False

    def snapshot(self):
        return copy.deepcopy(self.entries)

    def identity(self, entry):
        if self.fault == "backing_changed" and self.finished:
            return [1, 99, 2 * runner.GIB, 0, 0o600]
        return IDENTITY[:]

    def validate(self, entry):
        if self.fault == "untrusted":
            raise ValueError("runner_swap_file_identity_untrusted")
        if entry["used_kib"]:
            raise ValueError("runner_swap_is_not_an_unused_file")
        return self.identity(entry)

    def disable(self, entry):
        self.actions.append(("disable", entry["path"]))
        if self.fault == "disable_failed":
            raise RuntimeError("fixture sudo failure")
        self.entries = []

    def restore(self, entry):
        self.actions.append(("restore", entry["path"], entry["priority"]))
        if self.fault == "restore_failed":
            raise RuntimeError("fixture restore failure")
        self.entries = [copy.deepcopy(entry)]

    def run(self, command):
        assert self.entries == []
        self.actions.append(("run", tuple(command)))
        self.finished = True
        if self.fault == "device_left_active":
            self.entries = [dict(ENTRY, path="/dev/dm-0", kind="partition")]
        if self.fault == "interrupt":
            raise KeyboardInterrupt()
        return self.outcome


def execute(tmp_path, host, isolate=False):
    output = tmp_path / "receipt"
    code = runner.prepare_and_run(
        host, output, ["python", "qualification.py"], isolate_unused=isolate
    )
    receipt = json.loads((output / "swap-setup.json").read_text())
    assert receipt["full_v08_qualified"] is False
    assert receipt["eligible_for_publication"] is False
    assert receipt["existing_backing_removed"] is False
    assert receipt["persistent_config_changed"] is False
    assert len(receipt["source_sha256"]) == 3
    return code, receipt


def test_zero_swap_host_needs_no_isolation(tmp_path):
    host = FakeHost()
    code, receipt = execute(tmp_path, host)
    assert code == 0 and receipt["passed"]
    assert host.actions == [("run", ("python", "qualification.py"))]


def test_existing_host_swap_default_refusal_still_writes_receipt(tmp_path):
    host = FakeHost([ENTRY])
    code, receipt = execute(tmp_path, host)
    assert code != 0 and not receipt["passed"] and not receipt["comparison_command_started"]
    assert receipt["failures"] == ["existing_host_swap_requires_explicit_isolation"]
    assert host.actions == [] and host.entries == [ENTRY]


@pytest.mark.parametrize("priority", [-2, 0, 7, 32767])
def test_explicit_unused_file_isolation_restores_original_priority(tmp_path, priority):
    original = dict(ENTRY, priority=priority)
    host = FakeHost([original])
    code, receipt = execute(tmp_path, host, True)
    assert code == 0 and receipt["previous_swap_restored"] and receipt["passed"]
    assert host.entries == [original]
    assert [a[0] for a in host.actions] == ["disable", "run", "restore"]
    assert host.actions[-1][-1] == priority


@pytest.mark.parametrize("outcome", [1, 2, 130])
def test_failed_comparison_restores_but_cannot_pass(tmp_path, outcome):
    host = FakeHost([ENTRY], outcome=outcome)
    code, receipt = execute(tmp_path, host, True)
    assert code == outcome and not receipt["passed"] and receipt["previous_swap_restored"]
    assert host.entries == [ENTRY]


@pytest.mark.parametrize(
    "fault",
    [
        "disable_failed",
        "untrusted",
        "restore_failed",
        "backing_changed",
        "device_left_active",
        "interrupt",
    ],
)
def test_failures_preserve_evidence_and_never_claim_pass(tmp_path, fault):
    host = FakeHost([ENTRY], fault=fault)
    code, receipt = execute(tmp_path, host, True)
    assert code != 0 and not receipt["passed"] and receipt["failures"]
    if fault in ("backing_changed", "device_left_active"):
        assert not any(a[0] == "restore" for a in host.actions)
        assert receipt["cleanup_unproven"]
    if fault == "interrupt":
        assert receipt["previous_swap_restored"]


def test_busy_swap_is_not_disabled(tmp_path):
    host = FakeHost([dict(ENTRY, used_kib=1)])
    code, receipt = execute(tmp_path, host, True)
    assert code != 0 and not receipt["comparison_command_started"] and not host.actions


def test_multiple_devices_are_not_disabled(tmp_path):
    host = FakeHost([ENTRY, dict(ENTRY, path="/swapfile")])
    code, receipt = execute(tmp_path, host, True)
    assert code != 0 and not host.actions
    assert "multiple_existing_swap_devices_refused" in receipt["failures"]


def test_mutation_before_disable_is_refused(tmp_path):
    host = FakeHost([ENTRY])
    calls = 0

    def snapshot():
        nonlocal calls
        calls += 1
        return [dict(ENTRY, used_kib=0 if calls == 1 else 1)]

    host.snapshot = snapshot
    code, receipt = execute(tmp_path, host, True)
    assert code != 0 and not host.actions
    assert "runner_swap_changed_before_isolation" in receipt["failures"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "wrong header\n",
        "Filename Type Size Used Priority\na file 2 3 -2\n",
        "Filename Type Size Used Priority\na file 2 -1 -2\n",
        "Filename Type Size Used Priority\na file 2 0 40000\n",
        "Filename Type Size Used Priority\na\\040b file 2 0 -2\n",
        "Filename Type Size Used Priority\na file 2 0 -2 extra\n",
        "Filename Type Size Used Priority\na file 2 0 -2\na file 2 0 -2\n",
    ],
)
def test_malformed_inventory_is_rejected(text):
    with pytest.raises(ValueError):
        runner.parse_swaps(text)


def test_valid_inventory_is_read_only():
    assert runner.parse_swaps("Filename Type Size Used Priority\n") == []
    assert runner.parse_swaps(
        "Filename Type Size Used Priority\n/mnt/swapfile file 2097148 0 -2\n"
    ) == [ENTRY]


@pytest.mark.parametrize("fault", ["nonfile", "busy", "large", "priority", "lowram", "backing"])
def test_real_validation_rejects_unsafe_preparation(monkeypatch, fault):
    entry = ENTRY.copy()
    host = runner.SwapHost()
    monkeypatch.setattr(
        host, "identity", lambda _: IDENTITY[:] if fault != "backing" else [1, 2, 1024, 0, 0o600]
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *a, **k: "MemAvailable: " + ("1" if fault == "lowram" else "12000000") + " kB\n",
    )
    if fault == "nonfile":
        entry["kind"] = "partition"
    elif fault == "busy":
        entry["used_kib"] = 1
    elif fault == "large":
        entry["size_kib"] = 10 * runner.GIB // 1024
    elif fault == "priority":
        entry["priority"] = -3
    with pytest.raises(ValueError):
        host.validate(entry)


@pytest.mark.parametrize("fault", ["path", "symlink", "owner", "links", "writable", "directory"])
def test_real_file_identity_checks(monkeypatch, fault):
    entry = ENTRY.copy()
    if fault == "path":
        entry["path"] = "/unrelated/swapfile"
    monkeypatch.setattr(
        Path, "resolve", lambda self, **_: Path("/unrelated") if fault == "symlink" else self
    )
    mode = 0o100600 if fault != "directory" else 0o040700
    if fault == "writable":
        mode |= 0o020
    info = SimpleNamespace(
        st_mode=mode,
        st_uid=1 if fault == "owner" else 0,
        st_nlink=2 if fault == "links" else 1,
        st_dev=1,
        st_ino=2,
        st_size=2 * runner.GIB,
    )
    monkeypatch.setattr(Path, "lstat", lambda self: info)
    with pytest.raises(ValueError):
        runner.SwapHost().identity(entry)


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_ACTIONS", "false"),
        ("RUNNER_ENVIRONMENT", "self-hosted"),
        ("RUNNER_OS", "Windows"),
        ("GITHUB_RUN_ID", "bad"),
        ("GITHUB_RUN_ATTEMPT", "bad"),
    ],
)
def test_cli_refuses_non_hosted_or_invalid_identity(monkeypatch, key, value):
    env = dict(
        GITHUB_ACTIONS="true",
        RUNNER_ENVIRONMENT="github-hosted",
        RUNNER_OS="Linux",
        GITHUB_RUN_ID="1",
        GITHUB_RUN_ATTEMPT="1",
    )
    env[key] = value
    for name, item in env.items():
        monkeypatch.setenv(name, item)
    monkeypatch.setattr(runner.os, "getuid", lambda: 1001)
    monkeypatch.setattr(runner, "prepare_and_run", lambda *a, **k: pytest.fail("guard bypassed"))
    assert runner.main(["--isolate-unused-runner-swap", "true"]) == 2
