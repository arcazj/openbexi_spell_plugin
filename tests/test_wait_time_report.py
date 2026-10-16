"""Time-wait evidence needs actual durations, source and native observations."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from wait_time_report import qualify


@pytest.fixture(scope='module')
def proof():
    report = json.loads((ROOT / 'conformance/evidence/wait_time.json').read_bytes())
    return Path(report['raw']['path']), report['runtime_image']


def test_positional_waits_have_four_independent_dimensions(proof):
    report = qualify(*proof)
    assert len(report['qualified_contracts']) == 4 and len(report['checks']) == 8
    assert not report['full_v05_accepted']


@pytest.mark.parametrize('change', ['failed', 'missing', 'early', 'changed-source', 'missing-result'])
def test_altered_native_time_evidence_is_rejected(proof, tmp_path, change):
    original, image = proof
    raw = json.loads(original.read_bytes())
    shutil.copytree(original.parent / 'workspace', tmp_path / 'workspace')
    if change == 'failed':
        raw['checks']['relative:failure']['passed'] = False
    elif change == 'missing':
        del raw['checks']['absolute:recovery']
    elif change == 'early':
        raw['checks']['relative:positive']['result']['elapsed'][0] = 0
    elif change == 'changed-source':
        raw['checks']['absolute:positive']['source'] = 'assert True'
    else:
        (tmp_path / 'workspace/absolute-recovery/result.json').write_text('{}')
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(path, image)
