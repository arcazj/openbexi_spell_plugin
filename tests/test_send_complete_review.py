"""Reject altered native Send outcomes, limits, telemetry and receipts."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import send_complete_review as review


@pytest.fixture(scope='module')
def retained():
    proof=review.read(ROOT/'conformance/evidence/send_complete_review.json')
    path=Path(proof['raw']['path']);assert review.sha(path)==proof['raw']['sha256']
    specs=review.frozen('conformance/send_complete_cases.py',proof['source_revision']).CASES
    return proof,path,review.read(path),specs


def test_all_native_send_cases_retain_exact_evidence(retained):
    proof,path,raw,_=retained
    actual=review.review(path,Path(proof['overlay']),Path(proof['telemetry_overlay']),Path(proof['limit_overlay']),
                         proof['source_revision'],proof['runtime_image'])
    assert actual['checks']==proof['checks'] and len(actual['checks'])==12
    assert raw['artifacts']=={q.relative_to(path.parent/'workspace').as_posix():review.sha(q)
        for q in (path.parent/'workspace').rglob('*') if q.is_file()}


@pytest.mark.parametrize('mutation',['return-type','result-detail','limits','packet','execution-count','delay',
    'receipt','telemetry','numeric-pass','numeric-completion'])
def test_rebound_evidence_cannot_hide_changed_send_behavior(tmp_path,retained,mutation):
    proof,path,raw,specs=retained
    name='complex-send:positive' if mutation=='delay' else 'adjust-analog:boundary'
    row=deepcopy(raw['checks'][name]);project=tmp_path/name.replace(':','__')
    shutil.copytree(path.parent/'workspace'/project.name,project)
    if mutation=='return-type':next(c for c in row['observed']['calls'] if c['function']=='Send')['return_type']='bool'
    elif mutation=='result-detail':next(v for v in row['observed']['observations'] if v.get('actual_type')=='TmResult')['details']={}
    elif mutation=='limits':row['final_ground']['limits'][review.VOLTAGE]['HiRed']=28.5
    elif mutation=='packet':row['receipts'][0]['packet_sha256']='0'*64
    elif mutation=='execution-count':row['final_dss']['core']['commands_executed']=2
    elif mutation=='delay':next(v for v in row['observed']['observations'] if 'send_elapsed' in v)['send_elapsed']=0
    elif mutation=='receipt':
        db=sqlite3.connect(project/'driver.sqlite')
        try:db.execute("UPDATE effects SET state='PENDING' WHERE rowid=(SELECT max(rowid) FROM effects)");db.commit()
        finally:db.close()
    elif mutation=='telemetry':
        call=next(c for c in row['rpc'] if c['path'].endswith('/RefreshItem'))
        descriptor=review.p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TM'].methods_by_name['RefreshItem']
        answer=review.GetMessageClass(descriptor.output_type).FromString(bytes.fromhex(call['response']))
        answer.timestamp='2000-01-01 00:00:00.000000';call['response']=answer.SerializeToString().hex()
    elif mutation=='numeric-pass':row['passed']=1
    else:row['result']['completed']=1
    (project/'observed.json').write_text(json.dumps(row['observed']),encoding='utf-8')
    (project/'result.json').write_text(json.dumps(row['result']),encoding='utf-8')
    with pytest.raises(AssertionError):review.case_proof(name,specs[name],row,project)
