"""Contradict observed clocks and messages; a passing flag cannot qualify a wait."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from wait_interval_report import qualify


@pytest.fixture(scope='module')
def proof():
    report=json.loads((ROOT/'conformance/evidence/wait_interval.json').read_bytes())
    return Path(report['raw']['path']),report['runtime_image']


def test_native_scalar_and_staged_intervals_required(proof):
    report=qualify(*proof)
    assert len(report['qualified_contracts'])==4 and len(report['checks'])==12
    assert not report['full_v05_accepted']


@pytest.mark.parametrize('change',['missing','state','duration','interval','message','failure'])
def test_contradicted_interval_evidence_rejected(proof,tmp_path,change):
    original,image=proof;raw=json.loads(original.read_bytes())
    shutil.copytree(original.parent/'workspace',tmp_path/'workspace')
    row=raw['checks']['complex:positive'];project=tmp_path/'workspace/complex-positive'
    if change=='missing':del raw['checks']['simple:recovery']
    elif change=='state':row['states']=[r for r in row['states'] if r['status']!='WAITING']
    elif change=='duration':
        row['result']['ended']=row['result']['started']+.1
        (project/'result.json').write_text(json.dumps(row['result']))
    elif change in ('interval','message'):
        path=project/'events.json';events=json.loads(path.read_bytes())
        event=next(e for e in events if e.get('message',{}).get('fields',{}).get('Text')=='INTERVAL:complex:positive')
        if change=='interval':event['received_monotonic']+=1
        else:event['message']['fields']['Text']='wrong'
        path.write_text(json.dumps(events));row['events_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        row['progress']=[e for e in events if e.get('message',{}).get('fields',{}).get('Text')=='INTERVAL:complex:positive']
        times=[e['received_monotonic'] for e in row['progress']]
        row['progress_offsets']=[t-row['result']['started'] for t in times]
        row['progress_gaps']=[b-a for a,b in zip([row['result']['started'],*times],times)]
    else:
        row=raw['checks']['simple:failure'];row['result']['rejected']=[]
        (tmp_path/'workspace/simple-failure/result.json').write_text(json.dumps(row['result']))
    (tmp_path/'workspace/checks.json').write_text(json.dumps(raw['checks']))
    path=tmp_path/'result.json';path.write_text(json.dumps(raw))
    with pytest.raises((AssertionError,ValueError)):qualify(path,image)
