"""Historical fixtures must not weaken current ranging evidence checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from rng_baseline_review import verify_baseline


def recorded(family):
    return json.loads((ROOT / 'conformance/baselines' / (family + '_negative_controls.json')).read_bytes())


@pytest.mark.parametrize('family', ['rng', 'rng_state'])
def test_original_negative_controls_bind_exact_committed_sources(family):
    raw = recorded(family)
    original = deepcopy(raw)
    source = verify_baseline(raw, family)
    assert raw == original
    assert source['sha256'] == raw['inputs'][source['original_path']]


@pytest.mark.parametrize('family', ['rng', 'rng_state'])
@pytest.mark.parametrize('mutation', ['source', 'missing', 'dimension', 'contract', 'input'])
def test_changed_historical_controls_are_rejected(family, mutation):
    raw = recorded(family)
    key = next(iter(raw['checks']))
    if mutation == 'source':
        raw['checks'][key]['source'] += '\nassert True\n'
    elif mutation == 'missing':
        del raw['checks'][key]
    elif mutation == 'dimension':
        raw['checks'][key]['dimension'] = 'invented'
    elif mutation == 'contract':
        raw['checks'][key]['contracts'] = ['invented']
    else:
        name = 'conformance/' + ('rng_cases.py' if family == 'rng' else 'rng_state_cases.py')
        raw['inputs'][name] = '0' * 64
    with pytest.raises(AssertionError):
        verify_baseline(raw, family)


@pytest.mark.parametrize('family,key', [('rng', 'baseband-names:positive'),
                                      ('rng_state', 'on-demand:boundary')])
def test_current_fixture_cannot_be_substituted_into_old_evidence(family, key):
    from rng_cases import CASES as catalog
    from rng_state_cases import CASES as state
    raw = recorded(family)
    raw['checks'][key]['source'] = (catalog if family == 'rng' else state)[key]
    with pytest.raises(AssertionError):
        verify_baseline(raw, family)
