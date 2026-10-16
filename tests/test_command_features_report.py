"""Do not let rewritten reports turn unsupported command behavior into coverage."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'), str(ROOT/'driver_plugin/src')]
import command_features_report as report
from check import supported_check
from openbexi_spell_dss.codec import unpack, pack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p


def canonical():
    return json.loads((ROOT/'conformance/evidence/command_features.json').read_bytes())


def test_independent_command_diagnostics_bind_26_candidates_without_promoting():
    saved = canonical()
    actual = report.qualify(saved['manifest'])
    assert actual == saved and len(actual['candidate_contracts']) == 26
    assert len(actual['checks']) == 60+26*4
    assert actual['qualified_contracts'] == [] and not actual['full_v05_accepted']
    for contract in actual['candidate_contracts']:
        assert all(supported_check(actual, contract+':'+d, d) for d in report.DIMENSIONS)


@pytest.mark.parametrize('mutation', ['time-execution', 'critical-prompt', 'load-status', 'unicode-rpc', 'case-source'])
def test_semantic_forgery_is_rejected_even_after_container_hashes_are_updated(tmp_path, mutation):
    saved = canonical()
    manifest = deepcopy(saved['manifest'])
    kind = 'catalog' if mutation == 'critical-prompt' else 'scheduling'
    original = Path(manifest[kind]['path'])
    shutil.copytree(original.parent/'workspace', tmp_path/'workspace')
    shutil.copytree(original.parent/'inputs', tmp_path/'inputs')
    raw = json.loads(original.read_bytes())
    workspace = tmp_path/'workspace'
    if mutation == 'time-execution':
        row = raw['checks']['Time:positive']
        receipt = row['receipts'][-1]
        receipt['acknowledgement']['simulation_time_ns'] = 0
        # Both the exported JSON and the database now assert the same bad time.
        with sqlite3.connect(workspace/'Time-positive/dss.sqlite') as db:
            db.execute('UPDATE operations SET acknowledgement=? WHERE stage=?',
                       (json.dumps(receipt['acknowledgement']), 'ONBOARD_EXECUTION'))
    elif mutation == 'critical-prompt':
        row = raw['checks']['ConfirmCritical:positive']
        row['prompts'] = []
        path = workspace/'ConfirmCritical-positive/events.json'
        events = [e for e in json.loads(path.read_bytes()) if e.get('message', {}).get('id') != 'MSG_PROMPT']
        path.write_text(json.dumps(events), encoding='utf-8')
        row['events_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == 'load-status':
        row = raw['checks']['LoadOnly:positive']
        path = workspace/'LoadOnly-positive/events.json'
        events = json.loads(path.read_bytes())
        for event in events:
            fields = event.get('message', {}).get('fields', {})
            if fields.get('ItemType') == 'EXECUTION':fields['ItemValue'] = 'ONBOARD_EXECUTION'
        path.write_text(json.dumps(events), encoding='utf-8')
        row['events_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == 'unicode-rpc':
        row = raw['checks']['addInfo:encoding']
        wire = next(r for r in row['rpc'] if r['path'].endswith('_TC/SendCommand'))
        request = p.CommandDesc.FromString(bytes.fromhex(wire['request']))
        options = unpack(request.config)
        options['addInfo']['note'] = 'lost encoding'
        request.config.CopyFrom(pack(options))
        wire['request'] = request.SerializeToString().hex()
    else:
        row = raw['checks']['Time:failure']
        row['source'] += '\n# unreviewed replacement\n'
        (workspace/'Time-failure/main.py').write_text(row['source'], encoding='utf-8')
    (workspace/'checks.json').write_text(json.dumps(raw['checks']), encoding='utf-8')
    path = tmp_path/'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    manifest[kind].update(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises((AssertionError, ValueError, KeyError)):
        report.qualify(manifest)
