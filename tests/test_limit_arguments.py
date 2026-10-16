from copy import deepcopy
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'driver_plugin/src'))
from openbexi_dss_proxy.limit_arguments import normalize


def test_named_definitions_and_status_lists_are_copied_without_string_conversion():
    original = {'Limits': {'ID1': {'Nominal': ["A,'B' "+chr(0x3b1)], 'Active': False}}}
    saved = deepcopy(original)
    result = normalize(original)
    assert result == original
    result['Limits']['ID1']['Nominal'].append('changed')
    assert original == saved


@pytest.mark.parametrize('options,expected', [
    ({'Midpoint': 3.4, 'Tolerance': .1}, {'Midpoint': 3.4, 'Tolerance': .1}),
    ({'Delta': [.23, .3]}, {'Delta': [.23, .3]}),
    ({'Active': False}, {'Active': False}),
    ({'LoBoth': 10, 'HiBoth': 40}, {'LoBoth': 10, 'HiBoth': 40}),
    ({'Limits': [10, 40]}, {'LoRed': 10, 'LoYel': 10, 'HiYel': 40, 'HiRed': 40}),
    ({'Limits': [10, 20, 40, 30]}, {'LoRed': 10, 'LoYel': 20, 'HiYel': 30, 'HiRed': 40}),
    ({'Definition': {'Name': 'New name'}, 'Tolerance': 0}, {'Name': 'New name'}),
])
def test_original_argument_forms(options, expected):
    assert normalize(options) == {'Definition': expected}


@pytest.mark.parametrize('options', [
    {}, {'Definition': {}}, {'Limits': {}}, {'Definition': []}, {'Midpoint': 1},
    {'Definition': {'LoRed': 1}, 'LoRed': 2}, {'Limits': {'ID1': {'LoRed': 1}}, 'Select': 'ID1'},
    {'Limits': {'ID1': {}}}, {'Limits': [1, 2, 3]}, {'Expected': ['A']},
])
def test_invalid_or_ambiguous_argument_forms_do_not_mutate_input(options):
    saved = deepcopy(options)
    with pytest.raises(ValueError):normalize(options)
    assert options == saved
