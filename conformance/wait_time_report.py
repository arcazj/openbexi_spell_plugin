"""Qualify positional time waits using traced native procedures and clocks."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from wait_time_cases import CASES
from installed_provenance import verify_capture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report

CONTRACTS = {
    'relative': ['CMP-LRM244-EXAMPLE-078', 'CMP-LRM244-SECTION-4-6-1-065'],
    'absolute': ['CMP-LRM244-EXAMPLE-079', 'CMP-LRM244-SECTION-4-6-2-066'],
}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(path, image):
    raw = json.loads(path.read_bytes())
    validate_report(path, image, len(CASES))
    assert raw['passed'] and not raw['timed_out'] and set(raw['checks']) == set(CASES)
    runtime = raw['runtime_sources']['integrated']
    assert runtime is not None
    verify_capture(runtime, raw['inputs'])
    assert raw['host_inputs'] == {p.name: sha(p) for p in (ROOT / 'host_runtime/python').glob('*.py')}
    assert json.loads((path.parent / 'workspace/checks.json').read_bytes()) == raw['checks']
    checks = deepcopy(raw['checks'])
    for name, spec in CASES.items():
        row = checks[name]
        assert row['source'] == spec['source'] and row['dimension'] == spec['dimension']
        assert row['status'] == 'FINISHED' and not any(key.endswith('_error') for key in row)
        if spec['waiting']:
            assert any(state['status'] == 'WAITING' for state in row['states'])
        project = path.parent / 'workspace' / name.replace(':', '-')
        assert (project / 'main.py').read_text(encoding='utf-8') == spec['source']
        assert json.loads((project / 'result.json').read_bytes()) == row['result']
        for filename, key in (('native.log', 'native_log_sha256'), ('events.json', 'events_sha256')):
            assert sha(project / filename) == row[key]
        log = (project / 'native.log').read_text(encoding='utf-8')
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        row.update(contracts=CONTRACTS[name.split(':')[0]],
            oracle='LRM p56: exact two-second relative forms, fractional and zero waits, past and future absolute deadlines, rejected invalid input and subsequent successful waits. Native procedure assertions use independent monotonic/UTC clocks and the controller observes WAITING/FINISHED.')
    results = {name: row['result'] for name, row in checks.items()}
    assert len(results['relative:positive']['elapsed']) == 3
    assert all(2 <= seconds < 5 for seconds in results['relative:positive']['elapsed'])
    assert len(results['relative:boundary']['elapsed']) == 2
    assert all(.25 <= seconds < 3 for seconds in results['relative:boundary']['elapsed'])
    assert .5 <= results['relative:recovery']['elapsed'] < 3
    for family in CONTRACTS:
        assert len(results[family + ':failure']['rejected']) == 2
        assert len(results[family + ':recovery']['rejected']) == 1
    targets = results['absolute:positive']['targets'] + [results['absolute:recovery']]
    assert len(targets) == 3 and all(row['target'] <= row['finished'] < row['target'] + 3 for row in targets)
    inputs = dict(raw['inputs'])
    for name in ('conformance/wait_time_report.py', 'conformance/WAIT_TIME.md', 'tests/test_wait_time_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, inputs=inputs, checks=checks,
        qualified_contracts=[name for group in CONTRACTS.values() for name in group],
        raw=dict(path=str(path.resolve()), sha256=sha(path)),
        scope='LRM p56 positional relative/absolute time waits and Examples 78–79',
        exclusions=['Interrupted waits', 'Telemetry conditions', 'Full WaitFor function', 'Interval progression'],
        full_v05_accepted=False, full_v06_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.raw, args.image)
    output = ROOT / 'conformance/evidence/wait_time.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), contracts=4, checks=len(report['checks']))))


if __name__ == '__main__':
    main()
