"""Reject native group receipts or status evidence that contradicts retained data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
import command_group_review as report


def saved():
    return json.loads((ROOT/'distribution/evidence/group-block-native-review.json').read_bytes())


def test_accepts_frozen_native_group_capture_without_promoting_coverage():
    record = saved()
    result = report.review(Path(record['raw']['path']), Path(record['overlay_manifest']['path']).parent,
                           record['source_revision'], record['runtime_image'])
    assert result == record and len(result['observations']) == 19
    assert not result['qualified_contracts'] and not result['full_v05_accepted']


@pytest.mark.parametrize('mutation', ['member-state', 'wire-bytes', 'native-status', 'competitor', 'undeclared-module'])
def test_rejects_contradictory_group_evidence(tmp_path, mutation):
    record = saved()
    original = Path(record['raw']['path'])
    raw = deepcopy(json.loads(original.read_bytes()))
    shutil.copytree(original.parent/'workspace', tmp_path/'workspace')
    # Frozen runner inputs remain independently bound to Git and their captured copy.
    shutil.copytree(original.parent/'inputs', tmp_path/'inputs')
    workspace = tmp_path/'workspace'
    if mutation == 'member-state':
        raw['checks']['Group:failure']['member_results'][0]['members'][2]['state'] = 'SUCCEEDED'
    elif mutation == 'wire-bytes':
        raw['checks']['Block:positive']['receipts'][0]['packet_hex'] = '0000'
    elif mutation == 'native-status':
        path = workspace/'Block-failure/events.json'
        events = json.loads(path.read_bytes())
        for event in events:
            fields = event.get('message', {}).get('fields', {})
            if fields.get('ItemName') == 'CMD3' and fields.get('ItemType') == 'EXECUTION':
                fields.update(ItemStatus='SUCCESS', ItemValue='ONBOARD_EXECUTION')
        path.write_text(json.dumps(events), encoding='utf-8')
        raw['checks']['Block:failure']['events_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == 'competitor':
        raw['checks']['GroupTime:positive']['competitor']['after']['core']['commands_executed'] += 1
    else:
        raw['runtime_sources']['installed']['spell/undeclared_change.py'] = '0'*64
    (workspace/'checks.json').write_text(json.dumps(raw['checks']), encoding='utf-8')
    (workspace/'runtime.json').write_text(json.dumps(raw['runtime_sources']), encoding='utf-8')
    path = tmp_path/'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError, KeyError)):
        report.review(path, Path(record['overlay_manifest']['path']).parent,
                      record['source_revision'], record['runtime_image'])
