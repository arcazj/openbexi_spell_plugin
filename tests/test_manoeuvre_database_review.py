"""Literal native observations remain required even after metadata is rebound."""
import hashlib,json,shutil,sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from manoeuvre_database_review import review,CONTRACTS


@pytest.fixture(scope='module')
def proof():
    report=json.loads((ROOT/'conformance/evidence/manoeuvre_database_review.json').read_bytes())
    return Path(report['raw']['path']),Path(report['overlay']),report['source_revision'],report['runtime_image']


def test_all_eight_native_results_qualify_only_the_two_manoeuvre_contracts(proof):
    report=review(*proof)
    assert report['qualified_contracts']==CONTRACTS and len(report['checks'])==8
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation',[
    'missing-case','wrong-image','numeric-pass','changed-file','wrong-return-type',
    'changed-detached-value','wrong-location','unexpected-rpc','changed-ground','numeric-completion','false-composed-profile',
])
def test_rebound_but_contradicted_native_proof_is_rejected(proof,tmp_path,mutation):
    original,overlay,revision,image=proof
    raw=json.loads(original.read_bytes());workspace=tmp_path/'workspace'
    shutil.copytree(original.parent/'workspace',workspace)
    row=raw['checks']['readonly-positive'];project=workspace/'readonly-positive'
    if mutation=='missing-case':del raw['checks']['load-failure']
    elif mutation=='wrong-image':raw['runtime_image']='sha256:'+'0'*64
    elif mutation=='numeric-pass':row['passed']=1
    elif mutation=='changed-file':(project/'data/mmd/Man01/Part1.IMP').write_text('KEY 99\n')
    elif mutation=='wrong-return-type':row['observed']['calls'][0]['return_type']='DatabaseFile'
    elif mutation=='changed-detached-value':
        row=raw['checks']['readonly-boundary'];project=workspace/'readonly-boundary'
        row['observed']['observations'][0]={'actual':[0,False,'text','changed'],'expected':[0,False,'text','changed']}
    elif mutation=='wrong-location':
        p=project/'context-configured.xml';p.write_text(p.read_text().replace('ManeuverDB','OtherDB'))
    elif mutation=='unexpected-rpc':row['rpc'][0]['path']='/spell.driver.SPELLDriverInterface_MEM/CreateGoldenImage'
    elif mutation=='changed-ground':row['final_ground']['images']['unexpected']={}
    elif mutation=='false-composed-profile':
        raw['runtime_sources']['profile']='fresh-composed-manoeuvre-wheel/1'
        (workspace/'runtime.json').write_text(json.dumps(raw['runtime_sources']))
        overlay=None
    else:row['result']['completed']=1
    (project/'observed.json').write_text(json.dumps(row['observed']))
    (project/'result.json').write_text(json.dumps(row['result']))
    (workspace/'checks.json').write_text(json.dumps(raw['checks']))
    raw['artifacts']={p.relative_to(workspace).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in workspace.rglob('*') if p.is_file()}
    target=tmp_path/'result.json';target.write_text(json.dumps(raw))
    with pytest.raises(AssertionError):review(target,overlay,revision,image)
