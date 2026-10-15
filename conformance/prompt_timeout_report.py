"""Qualify only Example 118 from installed native observations and two rebuilds."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from installed_provenance import verify_capture
from prompt_timeout_cases import CASES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def qualify(raw_path, baseline_path, pair_path):
    raw = json.loads(raw_path.read_bytes())
    baseline = json.loads(baseline_path.read_bytes())
    pair = json.loads(pair_path.read_bytes())
    original_path = Path(baseline['raw']['path'])
    assert sha(original_path) == baseline['raw']['sha256']
    original = json.loads(original_path.read_bytes())
    for key in ('runtime_image', 'inputs', 'checks', 'controller_exit_code'):
        assert baseline[key] == original[key]
    validate_report(raw_path, raw['runtime_image'], len(CASES))
    assert raw['passed'] is True and raw['timed_out'] is False
    assert set(raw['checks']) == set(CASES)
    runtime = raw['runtime_sources']['integrated']
    assert runtime is not None
    verify_capture(runtime, raw['inputs'])
    expected_failures = {'default:positive', 'default:recovery'}
    assert len(baseline['checks']) == 7 and baseline['controller_exit_code'] == 1
    assert {k for k, v in baseline['checks'].items() if not v['passed']} == expected_failures
    assert baseline['runtime_image'] != raw['runtime_image']
    for name in expected_failures:
        row = baseline['checks'][name]
        assert row['error'].startswith('TimeoutError: Native timed prompt did not return')
        assert not row['answers'] and len(row['prompts']) == 1
        assert raw['checks'][name]['result']['elapsed'] >= 0.25

    assert pair['passed'] is True and pair['build_cache_enabled'] is False
    assert pair['native_build_network'] == 'none' and pair['same_build_repackaging'] is False
    expected = {'independent_native_rebuilds', 'native_artifacts_identical',
                'python_sources_identical', 'composition_identical',
                'wheel_bytes_identical', 'fresh_install_and_removal'}
    assert set(pair['checks']) == expected and all(v is True for v in pair['checks'].values())
    assert len(pair['packages']) == len(pair['installed']) == 2
    assert pair['packages'][0]['sha256'] == pair['packages'][1]['sha256']
    for label, package, installed in zip(('a', 'b'), pair['packages'], pair['installed']):
        assert package['native_runtime_tests'] == 23 and package['context_lifecycle_tests'] == 10
        assert package['native_artifacts'] == runtime['native_artifacts']
        assert package['python_sources'] == runtime['python_sources']
        assert package['composition'] == runtime['manifest']['composition']
        assert installed['tests'] == 8 and all(installed[k] == 0 for k in ('failures', 'errors', 'skips'))
        assert installed['no_build_tree'] and installed['uninstall_preserves_plain_python']
        assert installed['wheel_sha256'] == package['sha256']
        wheel = pair_path.parent / label / 'distribution/wheels' / package['wheel']
        assert sha(wheel) == package['sha256']

    for name, spec in CASES.items():
        row = raw['checks'][name]
        assert row['source'] == spec['source']
        assert row['status'] == spec.get('expected_status', 'FINISHED')
        if 'minimum_elapsed' in spec:
            assert row['result']['elapsed'] >= spec['minimum_elapsed']
        project = raw_path.parent / 'workspace' / name.replace(':', '-')
        assert (project / 'main.py').read_text(encoding='utf-8') == spec['source']
        assert sha(project / 'events.json') == row['events_sha256']
        assert not row.get('cleanup_error')
    report = dict(raw)
    report.update(qualified_contracts=['CMP-LRM244-EXAMPLE-118'],
        scope='Native timed default example, zero/omitted timeout, malformed input recovery, duplicate answer and cancellation controls',
        exclusions=['Empty defaults', 'Reminder timing without a default', 'Full Prompt contract',
                    'Generic procedure checkpoint/warm-start recovery'],
        raw=reference(raw_path), baseline=reference(baseline_path), independent_builds=reference(pair_path))
    report['inputs'] = {**raw['inputs'],
        'conformance/prompt_timeout_report.py': sha(Path(__file__)),
        'distribution/run_language_regressions.py': sha(ROOT / 'distribution/run_language_regressions.py')}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'conformance/evidence/prompt_timeout_baseline.json')
    parser.add_argument('--native-pair', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'conformance/evidence/prompt_timeout.json')
    args = parser.parse_args()
    report = qualify(args.result, args.baseline, args.native_pair)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(args.output), 'passed': True, 'contracts': report['qualified_contracts']}))


if __name__ == '__main__':
    main()
