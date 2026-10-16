"""Whole-database dependency selection cannot omit a format or read-only control."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from database_complete_report import combined_checks,ADDITIONAL,DIMENSIONS


@pytest.fixture
def components():
    def load(name):return json.loads((ROOT/'conformance/evidence'/name).read_bytes())
    formats=load('database_format_review.json')
    values=load('database_values_composed.json')
    procedure=load('proc_dictionary_composed.json')
    manoeuvre=load('manoeuvre_database_review.json')
    base=dict(passed=True,checks=manoeuvre['checks'],manoeuvre_review=manoeuvre)
    # Unit test the dependency map only. Native qualification separately requires
    # one real immutable image and a full sequence; these retained donors differ.
    for row in (base,formats,values,procedure):row['runtime_image']='unit-test-only'
    return base,formats,values,procedure


def test_all_five_additional_contracts_require_every_dimension(components):
    checks=combined_checks(*components)
    for identifier in ADDITIONAL:
        for dimension in DIMENSIONS:
            row=checks['CMP-LRM244-'+identifier+':'+dimension]
            assert row['passed'] and row['dimension']==dimension and row['dependencies']


@pytest.mark.parametrize('defect',['format-failure','missing-nested-time','readonly',
    'procedure-recovery','octal','image','summary'])
def test_aggregate_rejects_incomplete_or_mixed_components(components,defect):
    base,formats,values,procedure=deepcopy(components)
    if defect=='format-failure':formats['checks']['formats:keys-failure']['passed']=False
    elif defect=='missing-nested-time':del formats['checks']['formats:nested-time-boundary']
    elif defect=='readonly':base['manoeuvre_review']['checks']['readonly-failure']['passed']=False
    elif defect=='procedure-recovery':del procedure['checks']['procedure-dictionary:recovery']
    elif defect=='octal':values['checks']['import-recovery']['passed']=False
    elif defect=='image':formats['runtime_image']='different-image'
    else:values['passed']=False
    with pytest.raises((AssertionError,KeyError)):combined_checks(base,formats,values,procedure)
