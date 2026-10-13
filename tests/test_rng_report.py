"""A passing simulator observation cannot qualify conflicted manual semantics."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from rng_cases import METADATA
from rng_report import CONTRACTS, EXCLUDED, qualify
from check import supported_check


def recorded_raw():
    report=json.loads((ROOT/'conformance/evidence/rng.json').read_bytes())
    # Reconstruct the recorded associations before qualification exclusions.
    for key,row in report['checks'].items():
        row['contracts']=list(METADATA[key]['contracts'])
    return report


def test_only_catalog_rows_qualify_and_diagnostic_observations_remain():
    raw=recorded_raw()
    report=qualify(raw)
    assert len(report['checks'])==36
    assert set(report['qualified_contracts'])==CONTRACTS
    assert len(CONTRACTS)==3
    assert set(report['excluded_contracts'])==set(EXCLUDED)
    assert {c for row in report['checks'].values() for c in row['contracts']}==CONTRACTS
    assert report['checks']['start-single:boundary']['contracts']==[]
    assert report['checks']['start-single:boundary']['observed_contracts']==['CMP-LRM244-EXAMPLE-170']
    assert raw['checks']['start-single:boundary']['contracts']==['CMP-LRM244-EXAMPLE-170']
    for key,row in report['checks'].items():
        if row['contracts']:
            assert supported_check(report,key,row['dimension'])


@pytest.mark.parametrize('mutation',['failed','dimension','contract','missing','prompts'])
def test_failed_or_incomplete_evidence_is_rejected(mutation):
    report=recorded_raw()
    key='baseband-names:positive'
    if mutation=='failed':
        report['checks'][key]['passed']=False
    elif mutation=='dimension':
        report['checks'][key]['dimension']='failure'
    elif mutation=='contract':
        report['checks'][key]['contracts']=['CMP-LRM244-FUNCTION-ENABLERANGING']
    elif mutation=='missing':
        del report['checks'][key]
    else:
        report['checks']['policy:positive']['prompts']=[]
    with pytest.raises(AssertionError):
        qualify(report)
