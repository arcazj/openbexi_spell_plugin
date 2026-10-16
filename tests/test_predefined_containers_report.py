"""Reject container evidence contradicted by the retained native run."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from predefined_containers_report import qualify


@pytest.fixture(scope='module')
def proof():
    report=json.loads((ROOT/'conformance/evidence/predefined_containers.json').read_bytes())
    return [Path(report['raw'][name]['path']) for name in ('dta','ipc','child')]+[report['runtime_image']]


def test_predefined_containers_require_typed_client_and_child_evidence(proof):
    result=qualify(*proof)
    assert len(result['qualified_contracts'])==2 and len(result['checks'])==150
    assert not result['full_v05_accepted']


@pytest.mark.parametrize('change',['missing','not-resumed','wrong-value','wrong-type','failed-edit-accepted'])
def test_contradicted_predefined_container_evidence_is_rejected(proof,tmp_path,change):
    dta,ipc,child,image=proof
    raw=json.loads(ipc.read_bytes());shutil.copytree(ipc.parent/'workspace',tmp_path/'workspace')
    if change=='missing':del raw['checks']['IVARS:failure']
    elif change=='not-resumed':raw['resumed_status']='ERROR'
    elif change=='wrong-value':raw['checks']['ARGS:recovery']['actual']['DictContents']='count\x0599'
    elif change=='wrong-type':
        (tmp_path/'workspace/container-types.json').write_text(json.dumps({'ARGS':'dict','IVARS':'dict'}))
    else:raw['checks']['IVARS:failure']['actual']['Error']=False
    original=json.loads((tmp_path/'workspace/dta-edit-results.json').read_bytes())
    for key in original:original[key]=raw[key]
    (tmp_path/'workspace/dta-edit-results.json').write_text(json.dumps(original))
    path=tmp_path/'result.json';path.write_text(json.dumps(raw))
    with pytest.raises((AssertionError,ValueError)):qualify(dta,path,child,image)
