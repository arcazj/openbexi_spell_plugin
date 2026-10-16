"""The listener diagnostic must retain its actual source, probes and binary."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from context_snapshot_report import qualify, verify_export


@pytest.fixture(scope='module')
def evidence():
    record = json.loads((ROOT / 'conformance/evidence/context_snapshot.json').read_bytes())
    paths = {name:Path(row['path']) for name,row in record['raw'].items()}
    runtime = json.loads(paths['startup'].read_bytes())['runtime_sources']
    return record, paths, Path(record['export']['path']), runtime


def test_diagnostic_evidence_retains_all_controls(evidence):
    record, paths, directory, _ = evidence
    actual = qualify(paths, directory, Path(record['retained_failure']['path']),
                     source_revision='406bab3')
    assert actual['passed_checks'] == {'errors':8,'recovery':22,'startup':40}
    assert actual['qualified_contracts'] == [] and not actual['full_v05_accepted']
    assert actual['probes']['probes']['original']['observation']['coherent'] is False
    assert actual['probes']['probes']['patched']['observation']['coherent'] is True


@pytest.mark.parametrize('name', ['patched.C', 'context_snapshot_patches.py', 'compiled/SPELL-Listener',
    'compiled/incremental-build.json', 'probes/original-probe.cpp', 'probes/patched-run.log'])
def test_altered_export_is_rejected(evidence, tmp_path, name):
    _, _, original, runtime = evidence
    directory = tmp_path / 'export'
    shutil.copytree(original, directory)
    path = directory / name
    path.write_bytes(path.read_bytes() + b'altered')
    with pytest.raises((AssertionError, ValueError)):
        verify_export(directory, runtime)
