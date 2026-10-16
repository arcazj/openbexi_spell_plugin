"""Report reuse saves filesystem work without accepting stale or mixed evidence."""
import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

validate=runpy.run_path(str(Path(__file__).resolve().parents[1]/'conformance/check.py'))['validate']
DIMENSIONS=('positive','boundary','failure','recovery')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def evidence(tmp_path):
    (tmp_path/'conformance').mkdir()
    inventory={'rows':[{'id':str(i)} for i in range(763)]}
    path=tmp_path/'conformance/inventory.json';path.write_text(json.dumps(inventory))
    source=tmp_path/'source.txt';source.write_text('verified input')
    report={'runtime_image':'sha256:'+'1'*64,'inputs':{'source.txt':sha(source)},
        'checks':{d:dict(passed=True,dimension=d,contracts=['0','1'],oracle='fixture expectation') for d in DIMENSIONS}}
    report_path=tmp_path/'report.json';report_path.write_text(json.dumps(report))
    coverage={'inventory_sha256':sha(path),'rows':[dict(id=str(i),status='OPEN') for i in range(763)]}
    for row in coverage['rows'][:2]:
        row.update(status='QUALIFIED',evidence={d:dict(report='report.json',sha256=sha(report_path),check=d) for d in DIMENSIONS})
    return inventory,coverage,tmp_path,report


def test_shared_report_inputs_checked_once(evidence,monkeypatch):
    inventory,coverage,root,_=evidence
    original=Path.is_file;source=(root/'source.txt').resolve();calls=[]
    def counted(path):
        if path==source:calls.append(path)
        return original(path)
    monkeypatch.setattr(Path,'is_file',counted)
    gate=validate(inventory,coverage,root)
    assert gate['counts']=={'QUALIFIED':2,'OPEN':761}
    assert len(calls)==1


def test_later_contract_binding_still_verified(evidence):
    inventory,coverage,root,_=evidence
    coverage['rows'][1]['evidence']['failure']['check']='positive'
    with pytest.raises(ValueError,match='contract/dimension'):validate(inventory,coverage,root)


def test_second_report_conflicting_input_rejected(evidence):
    inventory,coverage,root,report=evidence
    other=copy.deepcopy(report);other['inputs']['source.txt']='0'*64
    path=root/'other.json';path.write_text(json.dumps(other))
    coverage['rows'][1]['evidence']={d:dict(report=path.name,sha256=sha(path),check=d) for d in DIMENSIONS}
    with pytest.raises(ValueError,match='Evidence input changed'):validate(inventory,coverage,root)


@pytest.mark.parametrize('change',['source','report','missing-source'])
def test_each_validation_rechecks_files(evidence,change):
    inventory,coverage,root,_=evidence
    assert validate(inventory,coverage,root)['counts']['QUALIFIED']==2
    if change=='source':(root/'source.txt').write_text('changed')
    elif change=='report':(root/'report.json').write_text('{}')
    else:(root/'source.txt').unlink()
    with pytest.raises(ValueError):validate(inventory,coverage,root)
