"""The routing regression requires the real malformed native call and no effects."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
import command_routing_review as report


def canonical():
    return json.loads((ROOT/'conformance/evidence/command_routing_validation.json').read_bytes())


def test_malformed_block_counterexample_and_native_recovery_are_reproducible():
    saved = canonical()
    assert report.review(Path(saved['candidate']['path']), saved['runtime_image'], saved['source_revision']) == saved


@pytest.mark.parametrize('mutation', ['effect-rpc', 'missing-rejection', 'source-body'])
def test_modified_routing_evidence_cannot_hide_a_command_effect(tmp_path, mutation):
    saved = canonical()
    original = Path(saved['candidate']['path'])
    raw = deepcopy(json.loads(original.read_bytes()))
    for name in saved['candidate_artifacts']:
        target = tmp_path/'workspace'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original.parent/'workspace'/name, target)
    if mutation == 'effect-rpc':
        raw['observations']['rpc'].append(dict(check=report.CASE, path='/spell.driver.SPELLDriverInterface_TC/SendBlock'))
        (tmp_path/'workspace/observations.json').write_text(json.dumps(raw['observations']), encoding='utf-8')
    elif mutation == 'missing-rejection':
        del raw['checks'][report.CASE]
    else:
        raw['checks'][report.CASE]['source'] = 'pass'
        checks = json.loads((tmp_path/'workspace/procedure/checks.json').read_bytes())
        checks[report.CASE]['source'] = 'pass'
        (tmp_path/'workspace/procedure/checks.json').write_text(json.dumps(checks), encoding='utf-8')
    path = tmp_path/'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError, KeyError)):
        report.review(path, saved['runtime_image'], saved['source_revision'])
