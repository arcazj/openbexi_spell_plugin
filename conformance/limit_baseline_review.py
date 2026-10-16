"""Distinguish genuine limit counterexamples from retained recorder failures."""
import hashlib
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'distribution'))
from evidence_sources import source_bytes
from installed_provenance import verify_capture

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ERRORS = {
    'hardsoft-properties': ('DriverException', 'Unsupported limit definition fields'),
    'multiple-definitions': ('DriverException', 'This profile has one limit definition: GENERIC'),
    'inactive-definition': ('SyntaxException', 'No limit values provided'),
    'midpoint-property': ('DriverException', 'Unavailable limit definition property'),
    'status-definition': ('DriverException', 'This profile implements HARDSOFT limits only'),
    'spike-definition': ('DriverException', 'This profile implements HARDSOFT limits only'),
    'step-definition': ('UnboundLocalError', 'limitDef'),
    'adjust-status': ('TypeError', "unsupported operand type(s) for -: 'list' and 'float'"),
    'load-file': ('TypeError', "_loadLimits() missing 1 required positional argument: 'config'"),
    'both-thresholds': ('SyntaxException', 'No limit definition has been provided'),
}


def review(path, revision, image):
    assert sha(path) == '5b5cea2e4a101277627215fbe1ff730b9f67bd5b2eff39eae494c1d346dc6e15'
    raw = read(path)
    assert raw['runtime_image'] == image and not raw['timed_out']
    assert raw['diagnostic_only'] and raw['qualified_contracts'] == []
    assert not raw['passed'] and raw['controller_exit_code'] == 1
    module = types.ModuleType('_limit_baseline')
    source = source_bytes(ROOT, 'conformance/limit_features_baseline_cases.py', revision)
    exec(compile(source, 'limit_features_baseline_cases.py', 'exec'), module.__dict__)
    assert set(raw['checks']) == set(module.CASES) == set(ERRORS)|{'alarm-controls', 'adjust-analog'}
    verify_capture(raw['runtime_sources']['integrated'], raw['inputs'])
    for name, digest in raw['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT, name, revision)).hexdigest() == digest, name
        assert sha(path.parent/'inputs'/name) == digest, name
    workspace = path.parent/'workspace'
    assert read(workspace/'runtime.json') == raw['runtime_sources']['integrated']
    assert read(workspace/'checks.json') == raw['checks']
    artifacts = {p.relative_to(workspace).as_posix(): sha(p) for p in workspace.rglob('*') if p.is_file()}
    observations = {}
    for name, row in raw['checks'].items():
        project = workspace/name
        assert row['source'] == module.CASES[name]['source'] == (project/'main.py').read_text(encoding='utf-8')
        assert sha(project/'native.log') == row['native_log_sha256']
        assert sha(project/'events.json') == row['events_sha256']
        actual = read(project/'observed.json')
        assert actual == row['observed'] and actual['calls']
        if name in ERRORS:
            kind, message = ERRORS[name]
            assert not row['passed'] and row['status'] == 'ERROR'
            assert any(call.get('error_type') == kind and message in call['error'] for call in actual['calls'])
        else:
            assert row['passed'] and row['status'] == 'FINISHED'
            assert all('returned' in call and 'error_type' not in call for call in actual['calls'])
        observations[name] = actual
    alarm = raw['checks']['alarm-controls']
    assert [call['function'] for call in observations['alarm-controls']['calls']] == ['SetLimits', 'DisableAlarm', 'EnableAlarm']
    assert all(call['returned'] is True for call in observations['alarm-controls']['calls'])
    assert sum(call['path'].endswith('/SetLimits') for call in alarm['rpc']) == 1
    assert 'limit_enabled' not in alarm['final_ground']
    values = raw['checks']['adjust-analog']['final_ground']['limits']['TMparam']
    assert values == {'LoRed':3.3, 'LoYel':3.3, 'HiYel':3.5, 'HiRed':3.5}
    return dict(passed=True, diagnostic_only=True, raw=dict(path=str(path.resolve()), sha256=sha(path)),
        source_revision=revision, runtime_image=image, observed=observations, baseline_inputs=raw['inputs'],
        artifacts=artifacts,
        failed_features=sorted(ERRORS),
        existing_support='Single numeric AdjustLimits condition with per-condition tolerance already succeeds',
        misleading_success='EnableAlarm/DisableAlarm return True without changing persistent alarm control',
        inputs={name:sha(ROOT/name) for name in ('conformance/limit_baseline_review.py',
                'tests/test_limit_baseline_review.py', 'conformance/LIMIT_FEATURE_PROFILE.md')},
        qualified_contracts=[], full_v05_accepted=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    result = review(args.raw, args.revision, args.image)
    target = ROOT/'conformance/evidence/limit_features_baseline.json'
    target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, counterexamples=len(ERRORS), output=str(target))))
