"""Failure-policy review must reject rewritten prompts, outcomes and packets."""
from copy import deepcopy
from pathlib import Path
import json
import shutil
import sqlite3
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import telemetry_policy_review as report

RAW=Path('C:/obtelemetry_policy/.qualification/telemetry-policy/a4d68b11bf594024aeb6bd4785c3696b/result.json')
REVISION='aae150a096d8bce407cfc8fe6eeb73b0d132fa93'


@pytest.fixture(scope='module')
def retained():
    assert report.sha(RAW)=='55c69433d9c001dfc2bdf607bf066dcf3e347b7c40974f4737e907e62ec03a37'
    return report.read(RAW),report.cases(REVISION)


def test_all_four_native_policy_cases_preserve_captured_artifacts(retained):
    raw,specs=retained
    workspace=RAW.parent/'workspace'
    for name,row in raw['checks'].items():
        assert report.case_proof(name,specs[name],row,workspace/name.replace(':','__'))['passed']
    assert raw['artifacts']=={p.relative_to(workspace).as_posix():report.sha(p) for p in workspace.rglob('*') if p.is_file()}


@pytest.mark.parametrize('mutation',['prompt','held','repaired-fault','validity','abort'])
def test_rebound_policy_evidence_cannot_hide_wrong_behavior(tmp_path,retained,mutation):
    raw,specs=retained
    name='failure-policy:'+('failure' if mutation=='abort' else 'positive')
    row=deepcopy(raw['checks'][name])
    project=tmp_path/name.replace(':','__')
    shutil.copytree(RAW.parent/'workspace'/project.name,project)
    if mutation=='prompt':
        events=report.read(project/'events.json')
        prompt=next(e['message']['fields'] for e in events if e.get('message',{}).get('id')=='MSG_PROMPT')
        prompt['ExpectedValues']='R\x04A\x04K'
        row['prompts'][0]['ExpectedValues']=prompt['ExpectedValues']
        (project/'events.json').write_text(json.dumps(events),encoding='utf-8')
        row['events_sha256']=report.sha(project/'events.json')
    elif mutation=='held':row['held'][0]['returned']=True
    elif mutation=='repaired-fault':
        db=sqlite3.connect(project/'dss.sqlite')
        try:
            db.execute('UPDATE scenarios SET faults=? WHERE id=?',
                (json.dumps({'telemetry_quality':'BAD'}),row['prompt_repairs'][0]['after']['scenario_id']))
            db.commit()
        finally:db.close()
    elif mutation=='validity':
        call=next(c for c in row['rpc'] if c['path'].endswith('/RefreshItem'))
        method=report.p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TM'].methods_by_name['RefreshItem']
        response=report.GetMessageClass(method.output_type).FromString(bytes.fromhex(call['response']))
        response.validity=True
        call['response']=response.SerializeToString().hex()
    else:row['status']='FINISHED'
    with pytest.raises(AssertionError):report.case_proof(name,specs[name],row,project)
