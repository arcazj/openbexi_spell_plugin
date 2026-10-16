"""Parent acceptance must preserve all independent child evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from check import DIMENSIONS, supported_check
from python_sections_report import CONTRACTS, compose, qualify


@pytest.fixture(scope='module')
def proof():
    record = json.loads((ROOT / 'conformance/evidence/python_sections.json').read_bytes())
    paths = {name: Path(row['path']) for name, row in record['raw'].items()}
    return paths, record['runtime_image']


def test_sections_require_all_observed_children_on_one_runtime(proof):
    report = qualify(*proof)
    assert report['qualified_contracts'] == CONTRACTS
    assert len(report['checks']) == 488 and not report['full_v05_accepted']
    for contract in CONTRACTS:
        for dimension in DIMENSIONS:
            assert supported_check(report, contract + ':' + dimension, dimension)


@pytest.fixture(scope='module')
def components(proof):
    paths, image = proof
    from database_scope_report import qualify as database
    from database_values_composed_report import qualify as values
    from legacy_compare_composed_report import qualify as comparison
    return json.loads(paths['python'].read_bytes()), {
        'comparison': comparison(paths['comparison'], image),
        'database': database(paths['database'], image),
        'values': values(paths['values'], paths['user'], image)}


@pytest.mark.parametrize('change', ['missing-child', 'failed-child', 'changed-source',
    'removed-dependency', 'wrong-runtime', 'missing-scope', 'migration-only', 'missing-dimension'])
def test_incomplete_or_migration_evidence_cannot_qualify_parent(components, change):
    python, supplements = deepcopy(components)
    key = 'CMP-LRM244-EXAMPLE-010:boundary'
    if change == 'missing-child':
        del python['checks'][key]
    elif change == 'failed-child':
        python['checks'][key]['passed'] = False
    elif change == 'changed-source':
        python['checks'][key]['source'] = 'assert True'
    elif change == 'removed-dependency':
        python['checks'][CONTRACTS[1] + ':boundary']['dependencies'].pop()
    elif change == 'wrong-runtime':
        supplements['comparison']['runtime_image'] = 'sha256:' + '0' * 64
    elif change == 'missing-scope':
        del supplements['database']
    elif change == 'migration-only':
        supplements['comparison']['checks']['failure']['legacy_spelling_supported'] = False
    else:
        del supplements['comparison']['checks']['recovery']
    with pytest.raises((AssertionError, ValueError)):
        compose(python, supplements)
