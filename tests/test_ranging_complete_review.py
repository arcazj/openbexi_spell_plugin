"""Reject rebound native ranging claims that contradict independent evidence."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import ranging_complete_review as report


@pytest.fixture(scope='module')
def retained():
    proof=report.read(ROOT/'conformance/evidence/ranging_complete_review.json')
    path=Path(proof['raw']['path'])
    assert report.sha(path)==proof['raw']['sha256']
    return path,report.read(path),report.frozen('conformance/ranging_complete_cases.py',proof['source_revision']).CASES,proof


def test_twenty_native_cases_preserve_all_captured_evidence(retained):
    path,raw,specs,proof=retained
    result=report.review(path,Path(proof['overlay']),proof['source_revision'],proof['runtime_image'])
    assert len(result['checks'])==20 and result['qualified_contracts']==[] and not result['full_v05_accepted']
    assert raw['artifacts']=={p.relative_to(path.parent/'workspace').as_posix():report.sha(p)
        for p in (path.parent/'workspace').rglob('*') if p.is_file()}


@pytest.mark.parametrize('mutation',['paths','schedule','status','return-type','return-value','numeric-pass','numeric-completion','receipt','extra-effect','baseband'])
def test_forged_ranging_outcomes_are_rejected(tmp_path,retained,mutation):
    path,raw,specs,_=retained
    name='baseband-batch:positive' if mutation=='baseband' else 'status:positive' if mutation=='status' else 'dual:positive'
    row=deepcopy(raw['checks'][name]);project=tmp_path/name.replace(':','__')
    shutil.copytree(path.parent/'workspace'/project.name,project)
    if mutation=='paths':row['final_ground']['ranging_paths']=report.PATHS[:1]
    elif mutation=='schedule':row['final_ground']['ranging_schedule_enabled']=True
    elif mutation=='status':row['observed']['calls'][0].update(returned='True',return_type='bool')
    elif mutation=='return-type':row['observed']['calls'][0]['return_type']='int'
    elif mutation=='return-value':row['observed']['calls'][0]['returned']='False'
    elif mutation=='numeric-pass':row['passed']=1
    elif mutation=='numeric-completion':row['result']['completed']=1
    elif mutation=='baseband':row['final_ground']['baseband']['DSS-BBE-1']['integration_ms']='1000'
    else:
        db=sqlite3.connect(project/'driver.sqlite')
        try:
            if mutation=='receipt':db.execute("UPDATE effects SET state='PENDING' WHERE rowid=(SELECT max(rowid) FROM effects)")
            else:db.execute("INSERT INTO effects SELECT session,procedure,?,authority,digest,state,receipt,created_ns FROM effects LIMIT 1",('f'*32,))
            db.commit()
        finally:db.close()
    (project/'observed.json').write_text(json.dumps(row['observed']),encoding='utf-8')
    (project/'result.json').write_text(json.dumps(row['result']),encoding='utf-8')
    with pytest.raises(AssertionError):report.case_proof(name,specs[name],row,project)
