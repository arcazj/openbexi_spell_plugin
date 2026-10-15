"""Run native prompt defaults and retain exact source, runtime and IPC evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from installed_provenance import input_paths, verify_capture
from prompt_timeout_cases import CASES

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    token = uuid.uuid4().hex
    output = ROOT / '.qualification/prompt-timeout' / token
    output.mkdir(parents=True)
    names = ['conformance/prompt_timeout_cases.py', 'conformance/prompt_timeout_controller.py',
             'conformance/run_prompt_timeout.py', 'conformance/inventory.json',
             'docs/reference/SPELL - Language Reference - 2.4.4.pdf',
             'docs/reference/SPELL2.6.10-src.zip', *input_paths(ROOT)]
    inputs = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                     '--format', '{{.Id}}'], text=True).strip()
    name = 'openbexi-prompt-timeout-' + token
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none',
                        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                        '--pids-limit', '256', '--entrypoint', 'python', image,
                        '-I', '/workspace/prompt_timeout_controller.py'], check=True, capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as bundle:
            for source in ('prompt_timeout_cases.py', 'prompt_timeout_controller.py', 'installed_provenance.py'):
                content = (ROOT / 'conformance' / source).read_bytes()
                item = tarfile.TarInfo(source)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                bundle.addfile(item, io.BytesIO(content))
        subprocess.run(['docker', 'cp', '-a', '-', name + ':/workspace'],
                       input=archive.getvalue(), check=True, capture_output=True)
        timed_out = False
        try:
            run = subprocess.run(['docker', 'start', '-a', name], capture_output=True, timeout=300)
            exit_code = run.returncode
        except subprocess.TimeoutExpired:
            timed_out, exit_code = True, -1
            subprocess.run(['docker', 'kill', name], capture_output=True, timeout=20, check=True)
        log = subprocess.run(['docker', 'logs', name], capture_output=True, timeout=20, check=True)
        (output / 'controller.log').write_bytes(log.stdout + log.stderr)
        subprocess.run(['docker', 'cp', name + ':/workspace/.', str(output / 'workspace')],
                       check=True, capture_output=True)
        check_path = output / 'workspace/checks.json'
        checks = json.loads(check_path.read_bytes()) if check_path.is_file() else {}
        runtime = json.loads((output / 'workspace/runtime.json').read_bytes())
        verify_capture(runtime, inputs)
        assert all(hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == v for n, v in inputs.items())
        report = {'passed': exit_code == 0 and set(checks) == set(CASES)
                            and all(c['passed'] for c in checks.values()),
                  'runtime_image': image, 'inputs': inputs, 'checks': checks,
                  'runtime_sources': {'integrated': runtime}, 'controller_exit_code': exit_code,
                  'timed_out': timed_out,
                  'full_v05_accepted': False, 'full_v06_accepted': False}
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'output': str(output), 'passed': report['passed'],
                          'failures': {k: v.get('error') for k, v in checks.items() if not v['passed']}}))
        return not report['passed']
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
