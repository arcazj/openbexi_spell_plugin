"""Native library identity and child lifecycle proof cannot be replaced by flags."""
import hashlib,json,shutil,sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from procedure_library_review import review


@pytest.fixture(scope='module')
def proof():
    r=json.loads((ROOT/'conformance/evidence/procedure_library_review.json').read_bytes())
    return Path(r['raw']['path']),Path(r['overlay']),r['source_revision'],r['runtime_image']


def test_all_twelve_original_child_results_and_native_modes_are_required(proof):
    result=review(*proof)
    assert len(result['checks'])==12 and result['qualified_contracts']==[]
    assert not result['full_v05_accepted']


@pytest.mark.parametrize('mutation',[
    'wrong-selected-child','wrong-native-instance','wrong-mode','early-child-start',
    'early-blocking-parent','changed-arguments','changed-priority-config','missing-case','missing-recovery',
])
def test_rebound_artifacts_still_require_independent_behavior(proof,tmp_path,mutation):
    original,overlay,revision,image=proof;raw=json.loads(original.read_bytes())
    workspace=tmp_path/'workspace';shutil.copytree(original.parent/'workspace',workspace)
    name='configured-priority'
    if mutation in ('wrong-mode','early-child-start','early-blocking-parent'):name='hidden-manual'
    elif mutation=='changed-arguments':name='complex-visible-manual'
    elif mutation=='missing-recovery':name='missing-then-nested'
    row=raw['checks'][name];project=workspace/name
    if mutation=='wrong-selected-child':row['child_result']['selected']='Bus'
    elif mutation=='wrong-native-instance':row['child_info']['Bus/procedure#0']=row['child_info'].pop('Validation/procedure#0')
    elif mutation=='wrong-mode':next(iter(row['child_info'].values()))['OpenMode']='{Automatic:True,Visible:True,Blocking:True}'
    elif mutation=='early-child-start':row['manual_observations'][0]['child_started']=True
    elif mutation=='early-blocking-parent':row['manual_observations'][0]['parent_returned']=True
    elif mutation=='changed-arguments':row['child_result']['arguments']['B']=0
    elif mutation=='changed-priority-config':
        row['configuration']['priorities']=['Bus','Payload','Validation']
        (project/'spell-library.json').write_text(json.dumps(row['configuration']))
    elif mutation=='missing-case':del raw['checks']['header-name']
    else:del row['rejected']
    (project/'child-result.json').write_text(json.dumps(row['child_result']))
    (workspace/'checks.json').write_text(json.dumps(raw['checks']))
    raw['artifacts']={p.relative_to(workspace).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in workspace.rglob('*') if p.is_file()}
    target=tmp_path/'result.json';target.write_text(json.dumps(raw))
    with pytest.raises(AssertionError):review(target,overlay,revision,image)
