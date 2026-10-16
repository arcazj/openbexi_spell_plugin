"""Independent numeric/status boundaries and atomic multi-definition changes."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'driver_plugin/src'))
from openbexi_spell_dss.limit_definitions import definition, modify, selected, property_value, classify


def hard(**values):
    return dict(LoRed=10, LoYel=20, HiYel=30, HiRed=40, **values)


def test_two_named_definitions_keep_metadata_and_active_selection_independent():
    values = {'Normal':hard(Active=True, Name='Nominal \u9065\u6e2c', Hysteresis=2),
              'Backup':hard(Active=False, Algorithm='TMparam1 < TMparam2 + TMparam3')}
    before = deepcopy(values)
    result = modify({}, updates=values)
    assert values == before and selected(result, 'ALL') == ['Normal', 'Backup']
    assert selected(result, 'ACTIVE') == ['Normal']
    assert selected(result, 'Backup') == ['Backup']
    assert result['Normal']['Name'] == 'Nominal \u9065\u6e2c' and result['Normal']['Hysteresis'] == 2
    updated = modify(result, patch={'HiRed':50})
    assert updated['Normal']['HiRed'] == 50 and updated['Backup']['HiRed'] == 40
    assert result['Normal']['HiRed'] == 40


def test_last_bad_definition_does_not_partially_change_earlier_members():
    original = modify({}, updates={'Normal':hard(), 'Backup':hard()})
    before = deepcopy(original)
    with pytest.raises(ValueError):
        modify(original, updates={'Normal':{'LoRed':0}, 'Backup':{'HiRed':-1}})
    assert original == before


def test_empty_legacy_profile_creates_one_generic_definition_and_recovers():
    original = {}
    with pytest.raises(ValueError):modify(original, patch={'LoRed':0})
    assert original == {}
    result = modify(original, patch=hard())
    assert list(result) == ['GENERIC'] and result['GENERIC']['Type'] == 'HARDSOFT'
    assert result['GENERIC']['Active'] is True


@pytest.mark.parametrize('reading,severity', [
    (9.999, 'Error'), (10, 'Warning'), (19.999, 'Warning'), (20, 'Nominal'),
    (25, 'Nominal'), (30, 'Nominal'), (30.001, 'Warning'), (40, 'Warning'), (40.001, 'Error')])
def test_hard_and_soft_boundaries_are_inclusive(reading, severity):
    assert classify(definition(hard()), reading) == severity


def test_status_strings_remain_exact_even_with_commas_quotes_spaces_and_unicode():
    row = definition({'Nominal':['A,B', "it's on", '\u9065\u6e2c'], 'Warning':'OFF', 'Error':['FAILED'], 'Ignore':[]})
    assert row['Type'] == 'STATUS'
    assert row['Nominal'] == ['A,B', "it's on", '\u9065\u6e2c']
    assert classify(row, 'A,B') == 'Nominal' and classify(row, 'A') == 'Error'
    assert classify(row, 'OFF') == 'Warning'
    assert property_value(row, 'Ignore') == []
    copied = property_value(row, 'Nominal');copied.append('CHANGED')
    assert 'CHANGED' not in row['Nominal']


def test_status_classes_cannot_overlap_or_accept_nonstring_values():
    for patch in ({'Nominal':['A'], 'Error':['A']}, {'Nominal':['A', 'A']}, {'Nominal':[1]}, {'Nominal':True}):
        with pytest.raises(ValueError):definition(patch)


@pytest.mark.parametrize('change,severity', [(-4,'Error'),(-3,'Nominal'),(0,'Nominal'),(2,'Nominal'),(2.001,'Error')])
def test_step_uses_independent_down_and_up_deltas(change,severity):
    row = definition({'Delta':[3,2]})
    assert row['Type'] == 'STEP' and classify(row, 10+change, 10) == severity
    assert classify(row, 1000) == 'Nominal'


def test_spike_uses_absolute_delta_and_keeps_zero_boundary_meaningful():
    row = definition({'Delta':2})
    assert classify(row, 12, 10) == classify(row, 8, 10) == 'Nominal'
    assert classify(row, 13, 10) == classify(row, 7, 10) == 'Error'
    zero = definition({'Delta':0})
    assert classify(zero, 10, 10) == 'Nominal' and classify(zero, 10.0001, 10) == 'Error'


def test_midpoint_round_trip_and_paired_thresholds_do_not_mutate_input():
    patch = {'Midpoint':10.0, 'Tolerance':.5}
    row = definition(patch)
    assert patch == {'Midpoint':10.0, 'Tolerance':.5}
    assert [row[k] for k in ('LoRed','LoYel','HiYel','HiRed')] == [9.5,9.5,10.5,10.5]
    assert property_value(row, 'Midpoint') == 10 and property_value(row, 'Tolerance') == .5
    updated = definition({'LoBoth':0, 'HiBoth':100}, row)
    assert [updated[k] for k in ('LoRed','LoYel','HiYel','HiRed')] == [0,0,100,100]
    extremes = definition({'LoRed':1e308,'LoYel':1e308,'HiYel':1.5e308,'HiRed':1.5e308})
    assert property_value(extremes, 'Midpoint') == 1.25e308


@pytest.mark.parametrize('patch', [
    {'Delta':-1}, {'Delta':[1]}, {'Delta':[True,1]}, {'Delta':float('inf')},
    {'LoRed':10**10000}, {'Active':1}, {'Hysteresis':-1}, {'Hysteresis':True},
    {'Hysteresis':1025}, {'Unknown':1}, {'Midpoint':10}, {'Midpoint':10,'Tolerance':-1},
    {'LoBoth':0,'LoRed':0}, {'Name':'bad\nname'}, {'Algorithm':'x'*1025},
])
def test_invalid_partial_changes_preserve_existing_definition(patch):
    original = definition(hard())
    before = deepcopy(original)
    with pytest.raises(ValueError):definition(patch, original)
    assert original == before


def test_capacity_unknown_selector_and_cross_type_update_are_explicit_errors():
    rows = modify({}, updates={str(n):hard() for n in range(16)})
    with pytest.raises(ValueError):modify(rows, updates={'overflow':hard()})
    with pytest.raises(ValueError):selected(rows, 'unknown')
    with pytest.raises(ValueError):modify(rows, selector='0', patch={'Type':'STATUS','Nominal':['NOMINAL']})
    with pytest.raises(ValueError):property_value(rows['0'], 'Nominal')
