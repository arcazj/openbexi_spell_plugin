"""Bind prompt-order and abort controls to the actual reproducible runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from child_modes_cases import CASES as MODES
from installed_provenance import verify_capture
from prompt_timeout_cases import CASES as PROMPTS
from prompt_timeout_report import qualify as qualify_timed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
sys.path.insert(0, str(ROOT / 'source_port'))
from run_language_regressions import validate_report
from prompt_control_patches import PREIMAGES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def qualify(stress_path, modes_path, timed_path, pair_path, abort_stress_path):
    timed = qualify_timed(timed_path, ROOT / 'conformance/evidence/prompt_timeout_baseline.json', pair_path)
    image = timed['runtime_image']
    runtime = timed['runtime_sources']['integrated']
    stress = json.loads(stress_path.read_bytes())
    modes = json.loads(modes_path.read_bytes())
    aborts = json.loads(abort_stress_path.read_bytes())
    for path, report, count in ((stress_path, stress, 24), (modes_path, modes, len(MODES)),
                                (abort_stress_path, aborts, 12)):
        validate_report(path, image, count)
        assert report['passed'] and not report['timed_out']
        captured = report['runtime_sources']['integrated']
        verify_capture(captured, report['inputs'])
        for name in ('native_artifacts', 'python_sources', 'manifest'):
            assert captured[name] == runtime[name], name
    assert stress['selection'] == 'duplicate-order'
    assert set(stress['checks']) == {f'duplicate-{index}:boundary' for index in range(24)}
    assert sha(stress_path.parent / 'workspace/prompt_timeout_cases.py') == stress['generated_cases_sha256']
    for name, row in stress['checks'].items():
        assert row['status'] == 'FINISHED' and row['result']['answer'] == 'B'
        assert row['answers'] == ['1', '0'] and len(row['prompts']) == 1
        assert row['source'] == PROMPTS['duplicate:boundary']['source']
        project = stress_path.parent / 'workspace' / name.replace(':', '-')
        assert (project / 'main.py').read_text(encoding='utf-8') == row['source']
        assert sha(project / 'events.json') == row['events_sha256']
        assert not row.get('cleanup_error')
    assert modes['selection'] == 'complete' and aborts['selection'] == 'abort-at-prompt'
    verify_modes(modes_path, modes, MODES)
    verify_modes(abort_stress_path, aborts, {f'blocking-abort-{index}': MODES['blocking-abort']
                                           for index in range(12)})
    native = runtime['manifest']['composition']['native']
    stages = [stage for stage in native['stages'] if stage['recipe'] == 'prompt_control_patches.py']
    changed = {name: row for stage in stages for name, row in stage['sources'].items()}
    assert set(changed) == set(PREIMAGES)
    for name, (original, before) in PREIMAGES.items():
        assert native['sources'][name]['original_sha256'] == original
        assert changed[name]['before_sha256'] == before
        assert changed[name]['after_sha256'] == native['sources'][name]['patched_sha256']
    retained = {}
    for name in ('prompt_order_baseline', 'prompt_order_stress_baseline', 'child_modes_baseline',
                 'prompt_controls_first_candidate'):
        path = ROOT / 'conformance/evidence' / (name + '.json')
        report = json.loads(path.read_bytes())
        assert report['passed'] is False
        assert sha(Path(report['raw']['path'])) == report['raw']['sha256']
        retained[name] = reference(path)
    return dict(passed=True, runtime_image=image, qualified_contracts=[],
        scope='24 conflicting-answer trials, 12 abort-at-prompt trials, nine child-mode controls and the complete timed-prompt suite; no additional inventory promotion',
        raw={name: reference(path) for name, path in (
            ('stress', stress_path), ('modes', modes_path), ('timed', timed_path),
            ('native_pair', pair_path), ('abort_stress', abort_stress_path))},
        native_sources={name: native['sources'][name] for name in PREIMAGES},
        native_stages=stages,
        recipe=native['recipes']['prompt_control_patches.py'], retained_failures=retained,
        inputs={name: sha(ROOT / name) for name in ('conformance/prompt_control_report.py',
            'conformance/PROMPT_CONTROLS.md', 'source_port/prompt_control_patches.py')},
        full_v05_accepted=False, full_v06_accepted=False)


def verify_modes(path, report, cases):
    assert set(report['checks']) == set(cases)
    assert report['host_inputs'] == {p.name: sha(p) for p in (ROOT / 'host_runtime/python').glob('*.py')}
    assert sha(path.parent / 'workspace/child_modes_cases.py') == report['generated_cases_sha256']
    for name, spec in cases.items():
        row = report['checks'][name]
        assert row['source'] == spec['parent'] and row['child_source'] == spec['child']
        assert row['parent_result'] == spec['expected_parent']
        observations = row['observations']
        assert observations[-1]['phase'] == 'terminal'
        assert observations[-1]['child_status'] == spec['outcome']
        assert observations[-1]['parent_status'] == 'FINISHED'
        if not spec['automatic']:
            manual = [r for r in observations if r['phase'] == 'before-manual-run']
            assert len(manual) == 3
            assert all(r['child_status'] == 'PAUSED' and not r['child_started'] for r in manual)
            assert all(r['parent_returned'] is (not spec['blocking']) for r in manual)
        if spec['hold']:
            held = [r for r in observations if r['phase'] == 'child-awaiting-input']
            assert len(held) == 3
            assert all(r['child_status'] == 'PROMPT' and r['parent_returned'] is (not spec['blocking']) for r in held)
            assert all(r['child_started'] for r in held)
        expected_mode = '{Automatic:%s,Visible:True,Blocking:%s}' % (spec['automatic'], spec['blocking'])
        assert row['child_info']['OpenMode'] == expected_mode
        instances = set(filter(None, row['inventory']['ExecutorList'].split('\x03')))
        assert len(instances) == 2 and row['child_instance'] in instances
        project = path.parent / 'workspace' / name
        for file, expected in (('main.py', spec['parent']), ('child.py', spec['child'])):
            assert (project / file).read_text(encoding='utf-8') == expected
        for file, key in (('events.json', 'events_sha256'), ('native.log', 'native_log_sha256')):
            assert sha(project / file) == row[key]
        assert not any(key.endswith('_error') for key in row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stress', 'modes', 'timed', 'native-pair', 'abort-stress'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = qualify(args.stress, args.modes, args.timed, args.native_pair, args.abort_stress)
    path = ROOT / 'conformance/evidence/prompt_controls.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(path), 'passed': True}))


if __name__ == '__main__':
    main()
