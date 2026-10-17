"""Contradicted native procedure metadata must not qualify a correction."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from proc_dictionary_report import qualify as _qualify

def qualify(*args):
    return _qualify(*args,source_revision='194f5925a7bb001eca957a653bd37203f2bf1638')


@pytest.fixture(scope='module')
def proof():
    report=json.loads((ROOT/'conformance/evidence/proc_dictionary.json').read_bytes())
    return [Path(report['raw'][name]['path']) for name in ('baseline','lifecycle','original')]+[report['runtime_image']]


def test_native_dictionary_diagnostic_requires_all_sixteen_cases(proof):
    report=qualify(*proof)
    assert len(report['checks'])==20 and len(report['candidate_contracts'])==10
    assert not report['qualified_contracts'] and not report['full_v05_accepted']


@pytest.mark.parametrize('change',['missing','reevaluated','persistent','parent','output-path','step','host'])
def test_contradicted_proc_metadata_is_rejected(proof,tmp_path,change):
    baseline,lifecycle,original,image=proof
    raw=json.loads(lifecycle.read_bytes())
    shutil.copytree(lifecycle.parent/'workspace',tmp_path/'workspace')
    if change=='missing':del raw['checks']['reopen:recovery']
    elif change=='reevaluated':raw['checks']['reload:positive']['phases'][1]['evaluations']=2
    elif change=='persistent':raw['checks']['reopen:positive']['phases'][1]['observed']['initial']['PRIVATE_VALUE']=1
    elif change=='parent':raw['checks']['child:positive']['child_result']['initial']['PARENT']='wrong#1'
    elif change=='output-path':raw['checks']['child:boundary']['fixture_paths']['output']=raw['checks']['child:boundary']['fixture_paths']['input']
    elif change=='step':raw['checks']['child:recovery']['child_result']['last']['previous']=None
    else:raw['host_inputs']['adapter.py']='0'*64
    (tmp_path/'workspace/checks.json').write_text(json.dumps(raw['checks']))
    path=tmp_path/'result.json';path.write_text(json.dumps(raw))
    with pytest.raises((AssertionError,ValueError)):qualify(baseline,path,original,image)
