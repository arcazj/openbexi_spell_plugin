"""Memory review must reject forged packets, catalog rows, reports and outcomes."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import memory_complete_review as report
from openbexi_spell_dss.codec import pack,unpack


@pytest.fixture(scope='module')
def retained():
    proof=report.read(ROOT/'conformance/evidence/memory_complete_review.json')
    path=Path(proof['raw']['path']);assert report.sha(path)==proof['raw']['sha256']
    catalog=report.read(path.parent/'workspace/fixture/dss/data/satellite_database.json')
    specs=report.frozen('conformance/memory_complete_cases.py',proof['source_revision']).CASES
    return path,report.read(path),catalog,specs,proof


def test_all_native_memory_cases_retain_evidence_bytes(retained):
    path,raw,catalog,specs,proof=retained
    result=report.review(path,Path(proof['overlay']),Path(proof['telemetry_overlay']),Path(proof['limit_overlay']),proof['source_revision'],proof['runtime_image'])
    assert len(result['checks'])==32 and result['qualified_contracts']==[] and not result['full_v05_accepted']
    assert raw['artifacts']=={p.relative_to(path.parent/'workspace').as_posix():report.sha(p)
        for p in (path.parent/'workspace').rglob('*') if p.is_file()}


@pytest.mark.parametrize('mutation',['lookup','packet','file','catalog','skip','comparison','effect','numeric-pass','numeric-completion'])
def test_rebound_memory_evidence_cannot_hide_changed_results(tmp_path,retained,mutation):
    path,raw,catalog,specs,_=retained
    name={'file':'report:positive','catalog':'tmtc:positive','skip':'lookup:boundary','comparison':'compare:recovery'}.get(mutation,'lookup:positive')
    row=deepcopy(raw['checks'][name]);project=tmp_path/name.replace(':','__')
    shutil.copytree(path.parent/'workspace'/project.name,project)
    if mutation=='lookup':
        call=next(c for c in row['rpc'] if c['path'].endswith('/MemoryLookup') and 'response' in c)
        call['response']=pack({'TM.POWER.BUS_VOLTAGE':29}).SerializeToString().hex()
    elif mutation=='packet':row['final_ground']['images']['reference']['sha256']='0'*64
    elif mutation=='file':(project/'data/mem/voltage.txt').write_text('forged report')
    elif mutation=='catalog':
        call=next(c for c in row['rpc'] if c['path'].endswith('/DatabaseLookup'))
        response=report.p.LookupAnswer.FromString(bytes.fromhex(call['response']))
        value=unpack(response.lookup);value['item_code']=2
        response.lookup.CopyFrom(pack(value));call['response']=response.SerializeToString().hex()
    elif mutation=='skip':
        call=next(c for c in row['observed']['calls'] if c.get('policy')=='SKIP')
        call.update(returned='True',return_type='bool')
    elif mutation=='comparison':
        call=next(c for c in row['rpc'] if c['path'].endswith('/CompareImages') and 'response' in c)
        from google.protobuf.wrappers_pb2 import BoolValue
        call['response']=BoolValue(value=False).SerializeToString().hex()
    elif mutation=='effect':
        db=sqlite3.connect(project/'driver.sqlite')
        try:db.execute("UPDATE effects SET state='PENDING' WHERE rowid=(SELECT max(rowid) FROM effects)");db.commit()
        finally:db.close()
    elif mutation=='numeric-pass':row['passed']=1
    else:row['result']['completed']=1
    (project/'observed.json').write_text(json.dumps(row['observed']),encoding='utf-8')
    (project/'result.json').write_text(json.dumps(row['result']),encoding='utf-8')
    with pytest.raises(AssertionError):report.case_proof(name,specs[name],row,project,catalog)
