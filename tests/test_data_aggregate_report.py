"""Whole data claims require every retained native component and dimension."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from data_aggregate_report import component_checks,scope_spelling,qualify,MINIMA,MAPPINGS


@pytest.fixture(scope='module')
def captured():
    manifest=json.loads((ROOT/'conformance/evidence/data_aggregate_inputs.json').read_bytes())
    raws={name:json.loads(Path(row['path']).read_bytes()) for name,row in manifest['raw'].items()}
    import hashlib
    for name,row in manifest['raw'].items():
        assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
    return raws,manifest['runtime_image']


def test_real_typed_values_native_edits_and_blackboard_capture(captured):
    raws,image=captured
    checks=component_checks(raws,image)
    assert len(checks)==24 and sum(MINIMA.values())==160
    for contract in MAPPINGS:
        assert {r['dimension'] for r in checks.values() if r['contracts']==[contract]}=={
            'positive','boundary','failure','recovery'}


@pytest.mark.parametrize('mutation',[
    'missing-component','missing-check','extra-check','false-check','numeric-true',
    'wrong-image','failed-controller','failed-overall','no-edit-continuation',
    'missing-dimension','wrong-case-name',
])
def test_partial_or_contradicted_components_cannot_close_whole_contracts(captured,mutation):
    originals,image=captured;raws=copy.deepcopy(originals)
    row=raws['data'];first=next(iter(row['checks']))
    if mutation=='missing-component':del raws['data-race']
    elif mutation=='missing-check':del row['checks'][first]
    elif mutation=='extra-check':row['checks']['invented']=copy.deepcopy(row['checks'][first])
    elif mutation=='false-check':row['checks'][first]['passed']=False
    elif mutation=='numeric-true':row['checks'][first]['passed']=1
    elif mutation=='wrong-image':row['runtime_image']='sha256:'+'0'*64
    elif mutation=='failed-controller':row['controller_exit']=1
    elif mutation=='failed-overall':row['passed']=False
    elif mutation=='no-edit-continuation':raws['dta-ipc']['continued_after_edits']=False
    elif mutation=='missing-dimension':
        for check in row['checks'].values():check['dimension']='positive'
    else:row['checks']['invented']=row['checks'].pop(first)
    with pytest.raises(AssertionError):component_checks(raws,image)


@pytest.mark.parametrize('state,passed,complete',[
    ('failed',False,True),('running',False,True),('completed',True,False),
])
def test_failed_running_and_selected_only_sequences_are_never_accepted(tmp_path,state,passed,complete):
    path=tmp_path/'result.json'
    path.write_text(json.dumps(dict(state=state,passed=passed,complete_sequence=complete)))
    with pytest.raises(AssertionError):qualify(path)


def test_singular_inventory_spelling_is_resolved_from_original_manual_and_source():
    proof=scope_spelling()
    assert proof['inventory_label']=='ClearSharedDataScope'
    assert proof['demonstrated_callable']=='ClearSharedDataScopes'
    assert proof['pages']==[99,104]
    assert proof['member_sha256']=='168836e0a4bc96f8e2a67b5190f532b2154d6be1d697f1f818341349c221e735'
