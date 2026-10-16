from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'driver_plugin/src'))
from openbexi_spell_dss.limit_algorithm import Algorithm


def lookup(name):
    if name not in ('TM1', 'TM2', 'TM3', 'TM.CORE.MODE'):raise ValueError('Unknown TM')


def test_original_activation_expression_and_dotted_catalog_reference():
    expression = Algorithm('TM1<TM2+TM3 and TM.CORE.MODE == "NOMINAL"', lookup)
    values = {'TM1': 3, 'TM2': 2, 'TM3': 2, 'TM.CORE.MODE': 'NOMINAL'}
    assert expression.references == set(values)
    assert expression.evaluate(values.__getitem__)
    values['TM1'] = 4
    assert not expression.evaluate(values.__getitem__)


def test_repeated_names_read_one_sample_and_booleans_short_circuit():
    calls = []
    def acquire(name):calls.append(name);return 4
    assert Algorithm('TM1 == TM1', lookup).evaluate(acquire)
    assert calls == ['TM1']
    assert Algorithm('True or TM2 > 1', lookup).evaluate(acquire)
    assert calls == ['TM1']


@pytest.mark.parametrize('expression', [
    'open("x")', 'TM1[0]', '[x for x in TM1]', 'TM1**10000', 'UNKNOWN>1',
    'lambda: 1', 'TM1.__class__', 'None', '1e999', '"x"*100000',
    'not '*20+'True', '+'.join(['1']*70),
])
def test_expressions_reject_calls_unknown_names_or_unbounded_operators(expression):
    with pytest.raises(ValueError):
        Algorithm(expression, lookup).evaluate(lambda name: 1)


@pytest.mark.parametrize('expression', ['1', '1 / 0 > 0', '1e308*1e308>0', 'TM1 and True', '"x"<1'])
def test_invalid_runtime_types_never_become_active(expression):
    with pytest.raises(ValueError):Algorithm(expression, lookup).evaluate(lambda name: 1)


def test_empty_expression_is_unconditional_and_numeric_comparisons_are_exact():
    assert Algorithm('', lookup).evaluate(lambda name: None)
    assert Algorithm('('*200+'True'+')'*200, lookup).evaluate(lambda name: None)
    assert Algorithm('-2 <= TM1/2 < +4', lookup).evaluate(lambda name: 6)
