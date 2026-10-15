"""A passing simulator observation cannot qualify conflicted manual semantics."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from rng_cases import CASES, METADATA
from rng_report import CONTRACTS, EXCLUDED, qualify
from check import supported_check


def recorded_raw():
    report=json.loads((ROOT/'conformance/evidence/rng.json').read_bytes())
    report['checks']={key:row for key,row in report['checks'].items() if key in CASES}
    # Reconstruct the recorded associations before qualification exclusions.
    for key,row in report['checks'].items():
        row['contracts']=list(METADATA[key]['contracts'])
    return report


def test_only_catalog_rows_qualify_and_diagnostic_observations_remain():
    raw=recorded_raw()
    report=qualify(raw)
    assert len(report['checks'])==12  # Eight native controls plus four explicit conjunctions.
    assert set(report['qualified_contracts'])==CONTRACTS
    assert len(CONTRACTS)==3
    assert set(report['excluded_contracts'])==set(EXCLUDED)
    assert {c for row in report['checks'].values() for c in row['contracts']}==CONTRACTS
    assert report['selection']=='catalog'
    assert report['runtime_sources']['overlay'] is None
    for key,row in report['checks'].items():
        if row['contracts']:
            assert supported_check(report,key,row['dimension'])
    for dimension in ('positive','boundary','failure','recovery'):
        aggregate='catalog-example174:'+dimension
        assert report['checks'][aggregate]['dependencies']==[
            'baseband-names:'+dimension,'antenna-names:'+dimension]
        report['checks']['antenna-names:'+dimension]['passed']=False
        assert not supported_check(report,aggregate,dimension)


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
        report['checks'][key]['prompts'].append({})
    with pytest.raises(AssertionError):
        qualify(report)


@pytest.mark.parametrize('mutation',['selection','overlay','bytes','stage','recipe'])
def test_catalog_requires_fresh_composed_ranging_sources(mutation):
    report=recorded_raw()
    runtime=report['runtime_sources']
    driver=runtime['integrated']['driver_composition']['manifest']
    if mutation=='selection':
        report['selection']='explicit'
    elif mutation=='overlay':
        runtime['overlay']={'manifest':{}}
    elif mutation=='bytes':
        runtime['installed']['openbexi_spell_dss/ground.py']='0'*64
    elif mutation=='stage':
        driver['stages']=[row for row in driver['stages'] if row['recipe']!='rng_state_patches.py']
    else:
        del driver['recipes']['rng_patches.py']
    with pytest.raises((AssertionError,ValueError)):
        qualify(report)
