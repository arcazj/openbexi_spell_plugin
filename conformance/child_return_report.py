"""Qualify the bounded p89 return clause using complete native mode/load controls."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from child_modes_cases import CASES as MODES
from child_start_report import qualify as qualify_start
from installed_provenance import verify_capture
from prompt_control_report import verify_modes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

CONTRACTS = ['CMP-LRM244-OUTCOME-STARTPROC-TRUE', 'CMP-LRM244-SECTION-4-16-1-6-114']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(start_path, modes_path, image):
    start = qualify_start(start_path, image)
    modes = json.loads(modes_path.read_bytes())
    validate_report(modes_path, image, len(MODES))
    assert modes['passed'] and not modes['timed_out'] and modes['selection'] == 'complete'
    verify_capture(modes['runtime_sources']['integrated'], modes['inputs'])
    verify_modes(modes_path, modes, MODES)
    for name in ('manifest', 'native_artifacts', 'python_sources', 'driver_composition'):
        assert modes['runtime_sources']['integrated'][name] == start['runtime_sources']['integrated'][name], name
    for name, spec in MODES.items():
        result = modes['checks'][name]['parent_result']
        actual = json.loads((modes_path.parent / 'workspace' / name / 'parent-result.json').read_bytes())
        assert actual == result == spec['expected_parent'], name
        assert result['rejected'] is spec['expected_parent']['rejected'], name
        if 'returned' in result:
            assert result['returned'] is True and actual['returned'] is True, name
        else:
            assert result['exception'] == 'DriverException' and 'returned' not in actual, name
    groups = {
        'positive': [('modes', name) for name in ('blocking-success', 'nonblocking-success')],
        'boundary': [('modes', name) for name in ('blocking-immediate', 'manual-blocking',
                                                'manual-nonblocking', 'nonblocking-late-error')],
        'failure': [('modes', name) for name in ('blocking-error', 'blocking-abort')]
                   + [('start', name) for name in start['checks'] if name.endswith('-failure')],
        'recovery': [('modes', 'blocking-recovery')]
                    + [('start', name) for name in start['checks'] if name.endswith('-recovery')],
    }
    assert sum(len(rows) for rows in groups.values()) == 17
    sources = {'modes': modes, 'start': start}
    checks = {}
    for dimension, observations in groups.items():
        dependencies = []
        for kind, name in observations:
            key = kind + '/' + name + ':' + dimension
            dependencies.append(key)
            assert sources[kind]['checks'][name]['passed']
            checks[key] = dict(passed=True, dimension=dimension, contracts=[],
                raw_check={'report': kind, 'check': name},
                oracle='Actual parent/child execution, native terminal states and retained result files; LRM pp88-89 timing and return expectations.')
        checks['return:' + dimension] = dict(passed=True, dimension=dimension,
            contracts=CONTRACTS, dependencies=dependencies,
            oracle='LRM p89: True follows successful blocking execution or nonblocking loading; require every observed mode and load condition for this dimension.')
    inputs = {}
    for report in (start, modes):
        for name, digest in report['inputs'].items():
            assert name not in inputs or inputs[name] == digest, name
            inputs[name] = digest
    for name in ('conformance/child_return_report.py', 'conformance/CHILD_RETURNS.md',
                 'conformance/prompt_control_report.py', 'tests/test_child_return_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=checks,
        qualified_contracts=CONTRACTS,
        raw={name: {'path': str(path.resolve()), 'sha256': sha(path)}
             for name, path in (('start', start_path), ('modes', modes_path))},
        scope='Explicit-import native profile: StartProc True outcome and p89 return-value section only',
        exclusions=['Interactive error policy', 'Hidden GUI behavior', 'Library priorities',
                    'Whole StartProc and global modifiers', 'Checkpoint recovery'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=Path, required=True)
    parser.add_argument('--modes', type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.start, args.modes, args.image)
    path = ROOT / 'conformance/evidence/child_returns.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(path), 'native_controls': 17, 'contracts': len(CONTRACTS)}))


if __name__ == '__main__':
    main()
