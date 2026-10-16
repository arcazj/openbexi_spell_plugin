"""Whole LIMIT clauses cannot omit a remaining row or an evidence dimension."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'conformance'))
import limit_full_report as report


def test_mapping_closes_exactly_the_fifty_two_original_remaining_limit_rows():
    report.verify_mapping()


@pytest.mark.parametrize('mutation',['missing-row','missing-feature','missing-dimension'])
def test_incomplete_mapping_is_rejected(monkeypatch,mutation):
    from limit_features_cases import CASES
    if mutation=='missing-row':
        mapping=dict(report.MAP);mapping.pop('FUNCTION-GETLIMITS');monkeypatch.setattr(report,'MAP',mapping)
    elif mutation=='missing-feature':
        mapping=dict(report.MAP);mapping['FUNCTION-GETLIMITS']=();monkeypatch.setattr(report,'MAP',mapping)
    else:
        monkeypatch.delitem(CASES,'named:failure')
    with pytest.raises(AssertionError):report.verify_mapping()
