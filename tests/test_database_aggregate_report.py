"""Whole operation claims cannot hide a failed native clause or mixed images."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from database_aggregate_report import validate_component,component_checks,qualify,MINIMA


@pytest.fixture(scope='module')
def captured():
    manifest=json.loads((ROOT/'conformance/evidence/database_aggregate_inputs.json').read_bytes())
    records={}
    for name,row in manifest['raw'].items():
        encoded=Path(row['path']).read_bytes()
        assert hashlib.sha256(encoded).hexdigest()==row['sha256']
        records[name]=json.loads(encoded)
    return records


@pytest.mark.parametrize('suite',MINIMA)
def test_real_native_component_contracts_are_complete(captured,suite):
    raw=captured[suite]
    validate_component(suite,raw,raw['runtime_image'])


def test_separate_diagnostic_images_cannot_qualify_an_aggregate(captured):
    assert len({r['runtime_image'] for r in captured.values()})==2
    with pytest.raises(AssertionError):component_checks(captured,captured['resource']['runtime_image'])


@pytest.mark.parametrize('mutation',[
    'missing','extra','failed','numeric-true','changed-source','changed-dimension',
    'wrong-image','controller-failed','timed-out','lost-file','false-prompt','bad-status',
])
def test_contradicted_user_database_evidence_is_rejected(captured,mutation):
    raw=copy.deepcopy(captured['user-database']);image=raw['runtime_image']
    row=raw['checks']['save:failure']
    if mutation=='missing':del raw['checks']['save:failure']
    elif mutation=='extra':raw['checks']['invented']=row
    elif mutation=='failed':row['passed']=False
    elif mutation=='numeric-true':row['passed']=1
    elif mutation=='changed-source':row['source']='assert True'
    elif mutation=='changed-dimension':row['dimension']='positive'
    elif mutation=='wrong-image':raw['runtime_image']='sha256:'+'0'*64
    elif mutation=='controller-failed':raw['controller_exit_code']=1
    elif mutation=='timed-out':raw['timed_out']=True
    elif mutation=='lost-file':raw['prompts']['prompt-abort']['files']={}
    elif mutation=='false-prompt':raw['prompts']['prompt-rename']['passed']=False
    else:raw['prompts']['prompt-abort']['status']='FINISHED'
    with pytest.raises(AssertionError):validate_component('user-database',raw,image)


@pytest.mark.parametrize('state,passed,complete',[
    ('failed',False,True),('running',False,True),('completed',True,False),
])
def test_incomplete_sequences_cannot_promote_database_operations(tmp_path,state,passed,complete):
    path=tmp_path/'result.json'
    path.write_text(json.dumps(dict(state=state,passed=passed,complete_sequence=complete)))
    with pytest.raises(AssertionError):qualify(path,None,None)
