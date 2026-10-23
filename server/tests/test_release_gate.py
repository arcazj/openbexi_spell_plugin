"""Publication preflight rejects partial, stale, altered or missing gate proof."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "v08_publication_preflight", ROOT / "scripts/check_v08_release.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
CANDIDATE, IDE = "a" * 40, "b" * 40


@pytest.fixture
def complete(tmp_path):
    (tmp_path / "docs/v0.8").mkdir(parents=True)
    (tmp_path / "server").mkdir()
    (tmp_path / "server/pyproject.toml").write_text('[project]\nversion="0.8.0"\n')
    manifest = dict(
        schema="openbexi.release-gates/1",
        version="0.8.0",
        publication_authorization=dict(request="Qualify and release full v0.8"),
        gates={},
    )
    for name, checks in gate.REQUIRED.items():
        receipt = dict(
            schema="openbexi.v08.acceptance-gate/1",
            gate=name,
            passed=True,
            candidate_commit=CANDIDATE,
            ide_commit=IDE,
            checks={key: True for key in checks},
            evidence=[dict(path="synthetic-unit-fixture", sha256="0" * 64)],
        )
        data = (json.dumps(receipt, sort_keys=True) + "\n").encode()
        path = tmp_path / "docs/v0.8" / ("fixture-" + name + ".json")
        path.write_bytes(data)
        manifest["gates"][name] = dict(
            qualified=True,
            receipt=dict(
                path=str(path.relative_to(tmp_path)), sha256=hashlib.sha256(data).hexdigest()
            ),
        )
    (tmp_path / "docs/v0.8/RELEASE_GATES.json").write_text(json.dumps(manifest))
    return tmp_path, manifest


def save_manifest(root, manifest):
    (root / "docs/v0.8/RELEASE_GATES.json").write_text(json.dumps(manifest))


def test_preflight_never_performs_publication_even_when_fixture_gates_are_complete(complete):
    root, _ = complete
    result = gate.assess(root, CANDIDATE, IDE)
    assert result["eligible_for_publication"] and not result["publication_performed"]


def test_native_component_receipt_cannot_replace_whole_family_gate(complete):
    root, manifest = complete
    data = (
        ROOT / "docs/v0.8/evidence/native-thread-barrier/qualification-summary.json"
    ).read_bytes()
    path = root / "docs/v0.8/component-receipt.json"
    path.write_bytes(data)
    manifest["gates"]["native_family"]["receipt"] = dict(
        path=str(path.relative_to(root)), sha256=hashlib.sha256(data).hexdigest()
    )
    save_manifest(root, manifest)
    result = gate.assess(root, CANDIDATE, IDE)
    assert not result["full_v08_qualified"] and not result["eligible_for_publication"]
    assert not result["gates"]["native_family"]["qualified"]


@pytest.mark.parametrize(
    "mutation", ["schema", "candidate", "ide", "partial", "one_not_boolean", "subset"]
)
def test_gate_receipt_cannot_promote_stale_partial_or_nonboolean_proof(complete, mutation):
    root, manifest = complete
    selected = manifest["gates"]["native_family"]["receipt"]
    path = root / selected["path"]
    receipt = json.loads(path.read_text())
    if mutation == "schema":
        receipt["schema"] = "openbexi.worker/2"
    elif mutation == "candidate":
        receipt["candidate_commit"] = "c" * 40
    elif mutation == "ide":
        receipt["ide_commit"] = "c" * 40
    elif mutation == "partial":
        del receipt["checks"]["before_run_child_admission"]
    elif mutation == "one_not_boolean":
        receipt["checks"]["before_run_child_admission"] = 1
    else:
        receipt["checks"] = {"observed_python_thread_held": True}
    data = json.dumps(receipt).encode()
    path.write_bytes(data)
    selected["sha256"] = hashlib.sha256(data).hexdigest()
    save_manifest(root, manifest)
    assert not gate.assess(root, CANDIDATE, IDE)["eligible_for_publication"]


def test_tampered_receipt_is_rejected_even_if_gate_says_qualified(complete):
    root, manifest = complete
    path = root / manifest["gates"]["security"]["receipt"]["path"]
    path.write_text(path.read_text() + " ")
    assert not gate.assess(root, CANDIDATE, IDE)["gates"]["security"]["qualified"]


def test_gate_manifest_cannot_omit_deployment_or_independent_review(complete):
    root, manifest = complete
    del manifest["gates"]["kubernetes"]
    save_manifest(root, manifest)
    with pytest.raises(ValueError):
        gate.assess(root, CANDIDATE, IDE)


def test_dirty_or_development_candidate_is_blocked(complete):
    root, _ = complete
    assert not gate.assess(root, CANDIDATE, IDE, dirty=True)["eligible_for_publication"]
    (root / "server/pyproject.toml").write_text('[project]\nversion="0.8.0.dev16"\n')
    assert not gate.assess(root, CANDIDATE, IDE)["eligible_for_publication"]


def test_later_evidence_commit_cannot_hide_runtime_or_companion_changes():
    assert gate.evidence_only("docs/v0.8/evidence/family/receipt.json")
    assert gate.evidence_only("docs/v0.8/TEST_REPORT.md")
    for path in (
        "server/src/runtime.py",
        "docs/v0.8/IDE_PAIR.json",
        "docs/v0.8/evidence/runtime.py",
        ".github/workflows/release.yml",
    ):
        assert not gate.evidence_only(path)
