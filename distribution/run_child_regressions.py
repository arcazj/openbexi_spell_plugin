"""Run all fourteen installed native child lifecycle controls in sequence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from child_lifecycle_report import qualify_run
from installed_provenance import input_paths, verify_capture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    if not args.image.startswith('sha256:') or len(args.image) != 71:
        parser.error('Select the immutable runtime image')
    output = ROOT / '.qualification/child-regressions' / uuid.uuid4().hex
    output.mkdir(parents=True)
    names = [*input_paths(ROOT), 'distribution/run_child_regressions.py',
             'conformance/child_lifecycle_report.py',
             *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'host_runtime/python').glob('*.py'))]]
    inputs = {name: sha(ROOT / name) for name in names}
    expected_host = {p.name: sha(p) for p in (ROOT / 'host_runtime/python').glob('*.py')}
    result = {'passed': False, 'state': 'running', 'runtime_image': args.image,
              'inputs': inputs, 'suites': [], 'full_v05_accepted': False, 'full_v06_accepted': False}
    runtime = None

    def save():
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')

    save()
    print('Evidence: ' + str(output), flush=True)
    for suite, options in (('lifecycle', []), ('removed', ['--externally-removed']), ('reopen', ['--reopen'])):
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'conformance/run_child_lifecycle.py'),
                   '--image', args.image, *options]
        stage = {'suite': suite, 'command': command, 'passed': False}
        print('Running ' + suite, flush=True)
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        log = output / (suite + '.log')
        log.write_text(run.stdout + '\n' + run.stderr, encoding='utf-8', newline='\n')
        stage.update(exit_code=run.returncode, log={'path': str(log), 'sha256': sha(log)})
        try:
            raw = Path(json.loads(run.stdout)['evidence']) / 'result.json'
            stage['raw'] = {'path': str(raw), 'sha256': sha(raw)}
            if run.returncode:
                raise ValueError('Native runner exited with ' + str(run.returncode))
            observed, reference = qualify_run(raw, args.image, suite)
            verify_capture(observed['runtime_sources'], inputs)
            if observed['host_inputs'] != expected_host:
                raise ValueError('Installed host differs from source inputs')
            if runtime is not None and runtime != observed['runtime_sources']:
                raise ValueError('Child suites used different installed artifacts')
            runtime = observed['runtime_sources']
            if any(sha(ROOT / name) != expected for name, expected in inputs.items()):
                raise ValueError('Source inputs changed during native qualification')
            stage.update(passed=True, checks=len(observed['cases']))
        except (AssertionError, KeyError, OSError, ValueError, TypeError) as error:
            stage['error'] = type(error).__name__ + ': ' + str(error)
            result['state'] = 'failed'
        result['suites'].append(stage)
        save()
        print(suite + ': ' + ('PASS' if stage['passed'] else stage['error']), flush=True)
        if not stage['passed']:
            return 1
    result.update(passed=True, state='completed', checks=sum(s['checks'] for s in result['suites']))
    save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
