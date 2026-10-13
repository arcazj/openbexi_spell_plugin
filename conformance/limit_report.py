"""Bind a conservative LIMIT checkpoint to retained native execution evidence."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from check import supported_check


ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'CMP-LRM244-'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')

# A function-wide GetLimits/SetLimits claim would obscure unsupported definition
# properties and types. Qualify only bounded clauses exercised in all dimensions.
GROUPS = {
    'injection': {
        'contracts': ('FUNCTION-SETGROUNDPARAMETER', 'EXAMPLE-084', 'SECTION-4-7-070'),
        'positive': ('inject.engineering', 'inject.list'),
        'boundary': ('inject.raw-negative', 'inject.boundary.int64.-9223372036854775808', 'inject.boundary.int64.9223372036854775807'),
        'failure': ('inject.reject.unknown-name', 'inject.reject.nonrepresentable', 'inject.reject.nonnumeric', 'inject.reject.int64.9223372036854775808', 'inject.failure-prompt-cancel'),
        'recovery': ('inject.recovery', 'inject.boundary.recovery'),
    },
    'restore': {
        'contracts': ('FUNCTION-RESTORENORMALLIMITS', 'EXAMPLE-106', 'SECTION-4-8-9-080'),
        'positive': ('restore.all-parameters',),
        'boundary': ('restore.all-parameters',),  # Includes a second, idempotent reset.
        'failure': ('reject.restore-extra-argument', 'reject.restore-unknown-modifier'),
        'recovery': ('limit.recovery',),
    },
    'alarm': {
        'contracts': ('FUNCTION-ISALARMED', 'EXAMPLE-107', 'SECTION-4-8-10-081'),
        'positive': ('alarm.live-dss-sample',),
        'boundary': tuple('alarm.' + str(value) for value in (9.999, 10.0, 19.999, 20.0, 25.0, 30.0, 30.001, 40.0, 40.001)),
        'failure': ('reject.alarm-extra-argument',),
        'recovery': ('limit.recovery',),
    },
    'hardsoft-definition': {
        'contracts': ('CONSTANT-LIMIT-TYPE-HARDSOFT', 'MODIFIER-DEFINITION', 'MODIFIER-LORED', 'MODIFIER-LOYEL', 'MODIFIER-HIYEL', 'MODIFIER-HIRED', 'EXAMPLE-096'),
        'positive': ('set.definition', 'set.partial-threshold'),
        'boundary': ('set.midpoint-definition-unchanged', 'set.boundary.int64'),
        'failure': ('reject.set-boolean', 'reject.set-unordered', 'reject.set-nan', 'reject.set-infinity', 'set.reject.int64.9223372036854775808', 'set.failure-prompt-cancel'),
        'recovery': ('limit.recovery',),
    },
    'midpoint': {
        'contracts': ('MODIFIER-MIDPOINT', 'EXAMPLE-099'),
        'positive': ('set.midpoint-selected',),
        'boundary': ('set.midpoint-definition-unchanged', 'set.midpoint-dictionary-unchanged'),
        'failure': ('set.reject.negative-tolerance',),
        'recovery': ('limit.recovery',),
    },
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_passed(path, suite):
    report = json.loads(path.read_bytes())
    assert report['suite'] == suite
    assert report['controller_exit_code'] == 0
    assert report['observations']['passed'] and report['observations']['status'] == 'FINISHED'
    assert report['checks'] and all(row['passed'] for row in report['checks'].values())
    if suite == 'limit':
        from limit_cases import CASES
    else:
        from obs_cases import CASES
    assert set(report['checks']) == set(CASES)
    for key, row in report['checks'].items():
        assert row['source'] == CASES[key], key
        assert len(row['prompts']) == len(row['expected_prompts']), key
        for prompt, plan in zip(row['prompts'], row['expected_prompts']):
            assert prompt['answer'] == plan['answer'] and set(prompt['choices']) == set(plan['choices']), key
    for name, expected in report['inputs'].items():
        assert digest(ROOT / name) == expected, name
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('limit_report', type=Path)
    parser.add_argument('obs_report', type=Path)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--numeric_failure', type=Path, required=True)
    parser.add_argument('--range_failure', type=Path, required=True)
    parser.add_argument('--retained_failure', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, default=ROOT / 'conformance/evidence/limit.json')
    args = parser.parse_args()
    report, obs = read_passed(args.limit_report, 'limit'), read_passed(args.obs_report, 'obs')
    assert report['runtime_image'] == obs['runtime_image']
    baseline = json.loads(args.baseline.read_bytes())
    numeric_failure = json.loads(args.numeric_failure.read_bytes())
    assert baseline['observations']['status'] == numeric_failure['observations']['status'] == 'FINISHED'
    assert not baseline['checks']['baseline.set-definition']['passed']
    assert not numeric_failure['checks']['inject.reject.nonnumeric']['passed']
    checks = report['checks']
    native_check_count = len(checks)
    raw_check_sha256 = {key: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
                       for key, value in checks.items()}
    # Original per-case annotations are navigational hints, not promotion.
    for row in checks.values():
        row['contracts'] = []
    for group, definition in GROUPS.items():
        for dimension in DIMENSIONS:
            dependencies = definition[dimension]
            assert all(checks[key]['passed'] for key in dependencies)
            leaves = []
            for key in dependencies:
                # One native scenario can contain several independently checked
                # behaviors (for example a reset followed by an idempotent reset).
                # Preserve its original source/result, and describe which
                # dimension this group uses rather than relabelling raw evidence.
                leaf = 'scenario:' + group + ':' + dimension + ':' + key
                checks[leaf] = deepcopy(checks[key])
                checks[leaf].update(dimension=dimension, contracts=[], original_scenario=key,
                    original_scenario_sha256=raw_check_sha256[key])
                leaves.append(leaf)
            checks[group + ':' + dimension] = dict(
                passed=True, dimension=dimension, dependencies=leaves,
                contracts=[PREFIX + value for value in definition['contracts']],
                oracle='All named actual native/DSS checks passed, with retained original-schema requests and persistent database observations; no unsupported-type rejection is treated as implementation.')
            assert supported_check(report, group + ':' + dimension, dimension)
    report['inputs']['conformance/limit_report.py'] = digest(Path(__file__))
    report['inputs']['conformance/check.py'] = digest(ROOT / 'conformance/check.py')
    report['original_source_archive'] = dict(path='docs/reference/SPELL2.6.10-src.zip',
        sha256=digest(ROOT / 'docs/reference/SPELL2.6.10-src.zip'))
    report['schema'] = 'openbexi.spell.limit-checkpoint/1'
    report['native_check_count'] = native_check_count
    report['qualified_contracts'] = sorted({contract for row in checks.values() for contract in row['contracts']})
    inventory = json.loads((ROOT / 'conformance/inventory.json').read_bytes())
    limit_ids = {row['id'] for row in inventory['rows'] if row['package'] == 'LIMIT'}
    assert set(report['qualified_contracts']) <= limit_ids
    assert all({row['dimension'] for row in checks.values() if contract in row['contracts']} == set(DIMENSIONS)
               for contract in report['qualified_contracts'])
    report['explicit_open_clauses'] = sorted(limit_ids - set(report['qualified_contracts']))
    report['scope'] = {
        'profile': 'Real GENERIC DSS driver, original-schema RPC and original native listener/context/executor; catalog-backed TMparam injection and live binary TM.POWER.BUS_VOLTAGE telemetry.',
        'definition': 'One actual persistent engineering HARDSOFT record per parameter, driver-defined identifier GENERIC, always active. Initial normal limits are empty and RestoreNormalLimits clears all modified records.',
        'limitations': [
            'No inactive or multiple definitions, STATUS/STEP/SPIKE implementation, activation algorithms, hysteresis, named limits-file loading, or alarm enable/disable.',
            'GetLimits and SetLimits function-wide clauses remain open; working single-definition selector/property and read/modify/write checks are retained without promoting their broader function claims.',
            'Partial threshold updates use read/merge/write; no concurrent multi-writer atomicity claim.',
            'The original generic-value protobuf encoding represents integers as signed Int64. Out-of-range integers are rejected before effects; finite floating-point thresholds retain their original encoding.',
            'This overlay is a development qualification image. Final clean wheel construction, RECORD metadata, integrated composition and independent distribution rebuilds remain separate gates.',
        ],
    }
    report['regressions'] = {
        'OBS': dict(path=str(args.obs_report.resolve()), sha256=digest(args.obs_report),
                    count=len(obs['checks']), runtime_image=obs['runtime_image'],
                    unchanged_assertion_inputs={key: value for key, value in obs['inputs'].items() if key.startswith('conformance/obs_')})}
    report['counterexamples'] = [dict(path=str(path.resolve()), sha256=digest(path),
        failed={key: row.get('error') for key, row in json.loads(path.read_bytes())['checks'].items() if not row['passed']})
        for path in (args.baseline, args.numeric_failure, args.range_failure)]
    report['retained_qualification_failures'] = [dict(path=str(path.resolve()), sha256=digest(path),
        runtime_image=json.loads(path.read_bytes())['runtime_image'],
        failed={key: row.get('error') for key, row in json.loads(path.read_bytes())['checks'].items() if not row['passed']})
        for path in args.retained_failure]
    report['raw_report'] = dict(path=str(args.limit_report.resolve()), sha256=digest(args.limit_report))
    report['full_v05_accepted'] = report['v06_dependency_satisfied'] = False
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.output), contracts=len(report['qualified_contracts']),
                         native_checks=native_check_count,
                         obs_checks=len(obs['checks']), sha256=digest(args.output)), indent=2))


if __name__ == '__main__':
    main()
