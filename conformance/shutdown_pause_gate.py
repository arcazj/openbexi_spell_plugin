"""Run the unchanged real IPC context gate with one declared native correction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside():
    output = Path('/shutdown-context-gate')
    output.mkdir()
    patch = Path('/shutdown-pause')
    manifest = json.loads((patch / 'result.json').read_bytes())
    assert manifest['passed'] and manifest['candidate']['result'] == dict(tests=10, failures=0)
    assert set(manifest['artifact']) == {'SPELL-Context'}
    for name, expected in manifest['prior_artifact'].items():
        assert sha(Path('/out') / name) == expected
        assert sha(patch / 'compiled' / name) == manifest['artifact'][name]
        shutil.copyfile(patch / 'compiled' / name, Path('/out') / name)
    prior = output / 'prior-fixture-markers'
    prior.mkdir()
    for path in Path('/out').glob('*.txt'):
        assert path.is_file() and not path.is_symlink()
        shutil.copyfile(path, prior / path.name)
        path.unlink()
    for name, target in [('SPELL-Context', 'SPELL-Context'), ('SPELL-Executor', 'SPELL-Executor_v3'),
                         ('SPELL-Executor_v3', 'SPELL-Executor_v3'), ('SPELL-Service', 'SPELL-Service_v3')]:
        link = Path('/source/bin') / name
        assert link.is_symlink() and link.readlink() == Path('/out') / target
        link.unlink()
    qualifier = Path('/context/qualify_context.py')
    env = dict(os.environ, OPENBEXI_CONTEXT_TEST_FILTER='all',
               ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', PYTHONMALLOC='malloc',
               SPELL_HOME='/source', SPELL_DATA='/out/executor-data', SPELL_CONFIG='/out/executor-config')
    result = subprocess.run([sys.executable, '-I', str(qualifier)], env=env, capture_output=True, timeout=450)
    (output / 'qualification.log').write_bytes(result.stdout + result.stderr)
    for path in [Path('/out/context-runtime.json'), *Path('/out').glob('*.log')]:
        shutil.copyfile(path, output / path.name)
    shutil.copytree('/out/context-logs', output / 'native-logs')
    gate = json.loads(Path('/out/context-runtime.json').read_bytes())
    expected = dict(tests=10, failures=0, errors=0, skips=0, lifecycle_runs=25, service_checkpoint_rejections=2)
    report = dict(passed=result.returncode == 0 and all(gate[k] == v for k, v in expected.items()),
                  exit_code=result.returncode, gate=gate, qualifier_sha256=sha(qualifier),
                  patch_manifest_sha256=sha(patch / 'result.json'),
                  patch=manifest, native_sha256=sha(Path('/out/SPELL-Context')),
                  inputs={'shutdown_pause_gate.py': sha(Path(__file__))},
                  full_v05_accepted=False, full_v06_accepted=False)
    report['outputs'] = {p.relative_to(output).as_posix(): sha(p) for p in output.rglob('*') if p.is_file()}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'gate': gate}), flush=True)
    return 0 if report['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--image')
    args = parser.parse_args()
    if args.inside:
        return inside()
    if not args.image or not args.image.startswith('sha256:'):
        parser.error('Select the exact diagnostic native image SHA')
    root = Path(__file__).resolve().parents[1]
    output = root / '.qualification/v0.6/shutdown-context' / uuid.uuid4().hex
    output.mkdir(parents=True)
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    assert image == args.image
    name = 'openbexi-shutdown-context-' + uuid.uuid4().hex
    report = dict(passed=False, image=image, inputs={'conformance/shutdown_pause_gate.py': sha(Path(__file__))})
    print(str(output), flush=True)
    try:
        subprocess.run(['docker', 'create', '--name', name, '--network', 'none', '--init',
                        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
                        '--entrypoint', 'python', image, '-I', '/shutdown_pause_gate.py', '--inside'], check=True, capture_output=True)
        subprocess.run(['docker', 'cp', str(Path(__file__)), name + ':/shutdown_pause_gate.py'], check=True, capture_output=True)
        with (output / 'container.log').open('wb') as log:
            started = subprocess.run(['docker', 'start', '-a', name], stdout=log, stderr=subprocess.STDOUT, timeout=490)
        report['exit_code'] = started.returncode
        archive = output / 'native-evidence.tar'
        with archive.open('wb') as out:
            subprocess.run(['docker', 'cp', name + ':/shutdown-context-gate', '-'], stdout=out, check=True)
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                target = output / member.name
                assert target.resolve().is_relative_to(output.resolve())
                if os.name == 'nt':
                    target = Path('\\\\?\\' + str(target.resolve()))
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    assert member.isfile(), member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.extractfile(member).read())
        native = json.loads((output / 'shutdown-context-gate/result.json').read_bytes())
        report.update(passed=started.returncode == 0 and native['passed'], native=native,
                      archive=dict(sha256=sha(archive), bytes=archive.stat().st_size))
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'report': str(output / 'result.json')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
