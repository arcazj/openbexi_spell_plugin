import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
validate = runpy.run_path(str(ROOT / 'conformance/check.py'))['validate']
supported_check = runpy.run_path(str(ROOT / 'conformance/check.py'))['supported_check']


def inputs():
    return tuple(json.loads((ROOT / 'conformance' / file).read_text(encoding='utf-8'))
                 for file in ('inventory.json', 'coverage.json'))


def test_historical_adapted_rows_do_not_promote_release():
    inventory, coverage = inputs()
    assert inventory['historical_counts'] == {'GAP':489,'PARTIAL':79,'ADAPTED':195}
    result = validate(inventory, coverage, ROOT)
    assert not result['accepted'] and not result['v0.6_dependency_satisfied']


@pytest.mark.parametrize('change', ['drop', 'duplicate', 'import_only', 'stale_inventory'])
def test_release_gate_rejects_incomplete_or_unbound_claims(change):
    inventory, coverage = inputs()
    if change == 'drop':
        coverage['rows'].pop()
    elif change == 'duplicate':
        coverage['rows'][0] = copy.deepcopy(coverage['rows'][1])
    elif change == 'import_only':
        coverage['rows'][0].update(status='QUALIFIED', evidence={'positive': {'imported':True}})
    else:
        coverage['inventory_sha256'] = '0' * 64
    with pytest.raises(ValueError):
        validate(inventory, coverage, ROOT)


def test_release_gate_rejects_failing_or_stale_evidence(tmp_path):
    inventory, coverage = inputs()
    (tmp_path / 'conformance').mkdir()
    raw = (ROOT / 'conformance/inventory.json').read_bytes()
    (tmp_path / 'conformance/inventory.json').write_bytes(raw)
    case = coverage['rows'][0]
    case['status'] = 'QUALIFIED'
    report = {'runtime_image':'sha256:' + '1' * 64, 'inputs':{'conformance/inventory.json':hashlib.sha256(raw).hexdigest()},
              'checks': {name: {'dimension':name,'contracts':[case['id']], 'passed':True,
                               'oracle':'independent fixture expectation'}
                         for name in ('positive','boundary','failure','recovery')}}
    path = tmp_path / 'evidence.json'
    for failure in ('failed', 'changed_source', 'changed_report'):
        current = copy.deepcopy(report)
        if failure == 'failed':
            current['checks']['failure']['passed'] = False
        elif failure == 'changed_source':
            current['inputs']['conformance/inventory.json'] = '0' * 64
        path.write_text(json.dumps(current), encoding='utf-8')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        case['evidence'] = {name:{'report':path.name,'sha256':digest,'check':name} for name in current['checks']}
        if failure == 'changed_report':
            path.write_text('{}', encoding='utf-8')
        with pytest.raises(ValueError):
            validate(inventory, coverage, tmp_path)


def test_migration_evidence_cannot_qualify_legacy_syntax_or_parent_sections():
    report = json.loads((ROOT/'conformance/evidence/python.json').read_text(encoding='utf-8'))
    legacy = 'CMP-LRM244-METHOD-DICTIONARY-HAS-KEY:positive'
    assert report['checks'][legacy]['passed']
    assert not supported_check(report, legacy, 'positive')
    parent = next(name for name, check in report['checks'].items() if legacy in check.get('dependencies', []))
    assert not supported_check(report, parent, 'positive')
    assert supported_check(report, 'CMP-LRM244-EXAMPLE-001:positive', 'positive')


def test_missing_failed_or_cyclic_section_dependencies_are_rejected():
    base = dict(passed=True, dimension='positive', oracle='all child cases independently pass')
    report = {'checks': {'parent': dict(base, dependencies=['child']), 'child': dict(base)}}
    assert supported_check(report, 'parent', 'positive')
    report['checks']['child']['passed'] = False
    assert not supported_check(report, 'parent', 'positive')
    report['checks']['child'].update(passed=True, dependencies=['parent'])
    with pytest.raises(ValueError, match='Cyclic'):
        supported_check(report, 'parent', 'positive')
    del report['checks']['child']
    assert not supported_check(report, 'parent', 'positive')
