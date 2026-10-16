"""Fresh procedure dictionary evidence must bind both lifecycle and native sources."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from proc_dictionary_composed_report import qualify


@pytest.fixture(scope='module')
def proof():
    report=json.loads((ROOT/'conformance/evidence/proc_dictionary_composed.json').read_bytes())
    return [Path(report['raw'][name]['path']) for name in ('baseline','lifecycle')]+[report['runtime_image']]


def test_fresh_dictionary_requires_both_native_suites(proof):
    report=qualify(*proof)
    assert report['passed'] and len(report['checks'])==20 and len(report['qualified_contracts'])==10
    assert report['diagnostic_donor']['commit']=='c22ba3d0f5e2362c2384f09036bfff30e83080b1'
    assert not report['full_v05_accepted']


@pytest.mark.parametrize('change',['missing','runtime','overlay','recipe','stage','reevaluated','persistent','parent','output-path'])
def test_contradicted_composed_proc_evidence_rejected(proof,tmp_path,change):
    baseline,lifecycle,image=proof
    raw=json.loads(lifecycle.read_bytes())
    shutil.copytree(lifecycle.parent/'workspace',tmp_path/'workspace')
    if change=='missing':del raw['checks']['reload:recovery']
    elif change=='runtime':raw['runtime_image']='sha256:'+'0'*64
    elif change=='overlay':raw['diagnostic_overlay']=True
    elif change=='recipe':raw['runtime_sources']['integrated']['manifest']['composition']['native']['recipes']['proc_dictionary_patches.py']['sha256']='0'*64
    elif change=='stage':
        stages=raw['runtime_sources']['integrated']['manifest']['composition']['native']['stages']
        stages[:]=[s for s in stages if s['recipe']!='proc_dictionary_patches.py']
    elif change=='reevaluated':raw['checks']['reload:positive']['phases'][1]['evaluations']=2
    elif change=='persistent':raw['checks']['reload:failure']['phases'][1]['observed']['initial']['PRIVATE_VALUE']=1
    elif change=='parent':raw['checks']['child:positive']['child_result']['initial']['PARENT']='wrong#1'
    else:raw['checks']['child:boundary']['fixture_paths']['output']=raw['checks']['child:boundary']['fixture_paths']['input']
    (tmp_path/'workspace/checks.json').write_text(json.dumps(raw['checks']))
    path=tmp_path/'result.json';path.write_text(json.dumps(raw))
    with pytest.raises((AssertionError,ValueError)):qualify(baseline,path,image)
