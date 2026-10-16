"""Aggregate evidence uses the release validator's actual dependency semantics."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'conformance'))
from aggregate_support import link_components
from check import supported_check


def fixture():
    return ({'clause':dict(passed=True,dimension='failure',contracts=['clause'],oracle='Required clause',
        dependencies=[dict(report='native',check='reject')])},
        {'native':{'checks':{'reject':dict(passed=True,dimension='failure',oracle='Original native rejection')}}})


def test_real_release_validator_accepts_links_and_rejects_failed_nested_evidence():
    checks,reviews=fixture();linked=link_components(checks,reviews)
    assert supported_check({'checks':linked},'clause','failure')
    leaf,=linked['clause']['dependencies']
    assert isinstance(leaf,str) and linked[leaf]['source_check']=={'report':'native','check':'reject'}
    linked[leaf]['passed']=False
    assert not supported_check({'checks':linked},'clause','failure')


@pytest.mark.parametrize('change',[{'passed':False},{'dimension':'positive'},
    {'legacy_spelling_supported':False},{'evidence_kind':'migration-and-rejection'}])
def test_failed_or_unsupported_source_cannot_become_a_supported_leaf(change):
    checks,reviews=fixture();reviews['native']['checks']['reject'].update(change)
    with pytest.raises(AssertionError):link_components(checks,reviews)
