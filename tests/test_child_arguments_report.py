"""Argument evidence must preserve actual native child execution and sources."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from child_arguments_report import CONTRACTS, qualify


def raw_path():
    canonical=json.loads((ROOT/'conformance/evidence/child_arguments.json').read_bytes())
    return Path(canonical['raw']['path'])


def test_native_arguments_qualify_only_the_declared_examples_and_syntax():
    report=qualify(raw_path())
    assert set(report['qualified_contracts'])==CONTRACTS
    assert len(report['checks'])==10
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation',['failed','missing','source','contract','child','host','runtime','prompt'])
def test_incomplete_or_altered_argument_evidence_is_rejected(tmp_path,mutation):
    report=json.loads(raw_path().read_bytes())
    key='arguments:positive'
    if mutation=='failed':
        report['checks'][key]['passed']=False
    elif mutation=='missing':
        del report['checks'][key]
    elif mutation=='source':
        report['checks'][key]['source']='assert True'
    elif mutation=='contract':
        report['checks'][key]['contracts']=['CMP-LRM244-FUNCTION-STARTPROC']
    elif mutation=='child':
        report['checks'][key]['child_instances']=[]
    elif mutation=='host':
        report['host_inputs']={}
    elif mutation=='runtime':
        report['runtime_sources']['integrated']=None
    else:
        report['checks'][key]['prompts']=[{}]
    target=tmp_path/'result.json'
    target.write_text(json.dumps(report))
    with pytest.raises((AssertionError,ValueError)):
        qualify(target)
