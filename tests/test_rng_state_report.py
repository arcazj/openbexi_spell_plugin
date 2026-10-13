"""The state correction records evidence without promoting library contracts."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from rng_state_report import qualify


def recorded():
    return json.loads((ROOT/'conformance/evidence/rng_state.json').read_bytes())


def test_corrected_profile_promotes_no_rows():
    report=qualify(recorded())
    assert len(report['checks'])==21
    assert report['qualified_contracts']==[]
    assert all(row['contracts']==[] for row in report['checks'].values())
    assert not report['full_v05_accepted'] and not report['v06_dependency_satisfied']


@pytest.mark.parametrize('mutation',['failed','dimension','contract','missing','source','prompts'])
def test_bad_or_overstated_evidence_is_rejected(mutation):
    raw=recorded()
    key=next(iter(raw['checks']))
    row=raw['checks'][key]
    if mutation=='failed':
        row['passed']=False
    elif mutation=='dimension':
        row['dimension']='wrong'
    elif mutation=='contract':
        row['contracts']=['CMP-LRM244-FUNCTION-ENABLERANGING']
    elif mutation=='missing':
        del raw['checks'][key]
    elif mutation=='source':
        row['source']='assert True'
    else:
        row['prompts'].append({})
    with pytest.raises(AssertionError):
        qualify(raw)
