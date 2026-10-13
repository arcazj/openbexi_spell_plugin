"""Run traced Until/Message procedures through the original native scheduler."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from scheduler_scenarios import SCENARIOS
from scheduler_checks import qualify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-dss:v05-cmd-02')
    parser.add_argument('--scenario', action='append')
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v0.5/scheduler')
    args = parser.parse_args()
    selected = {key: value for key, value in SCENARIOS.items()
                if args.scenario is None or key in args.scenario}
    assert selected
    output = args.output.resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    inputs = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        'conformance/scheduler_scenarios.py', 'conformance/scheduler_controller.py', 'conformance/run_scheduler.py',
        'conformance/scheduler_checks.py', 'conformance/SCHEDULER.md',
        'source_port/scheduler_patches.py','conformance/scheduler_native_build.py',
        'conformance/scheduler_native.Dockerfile','distribution/incremental_native.py',
        'conformance/inventory.json', 'docs/reference/SPELL - Language Reference - 2.4.4.pdf',
        'docs/reference/SPELL2.6.10-src.zip')}
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                    '--format', '{{.Id}}'], text=True).strip()
    name = 'openbexi-scheduler-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
            '--entrypoint', 'python', image, '-I', '/workspace/controller.py'],
            check=True, capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as bundle:
            for target, content in (
                ('controller.py', (ROOT / 'conformance/scheduler_controller.py').read_bytes()),
                ('scenarios.json', json.dumps(selected).encode()),
            ):
                item = tarfile.TarInfo(target)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                bundle.addfile(item, io.BytesIO(content))
        subprocess.run(['docker', 'cp', '-a', '-', name + ':/workspace'],
                       input=archive.getvalue(), check=True, capture_output=True)
        run = subprocess.run(['docker', 'start', '-a', name], capture_output=True,
                             timeout=60 * len(selected) + 60)
        (output / 'controller.log').write_bytes(run.stdout + run.stderr)
        subprocess.run(['docker', 'cp', name + ':/workspace/.', str(output / 'workspace')],
                       check=True, capture_output=True)
        observations = json.loads((output / 'workspace/observations.json').read_bytes())
        assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
                   for path, digest in inputs.items()), 'Inputs changed during native execution'
        report = dict(runtime_image=image, inputs=inputs,
                      runtime_sources=json.loads((output / 'workspace/runtime.json').read_bytes()),
                      controller_exit_code=run.returncode)
        manifest=report['runtime_sources'].get('scheduler_manifest')
        if manifest:
            for name,path in (('scheduler_patches.py','source_port/scheduler_patches.py'),
                              ('scheduler_native_build.py','conformance/scheduler_native_build.py'),
                              ('incremental_native.py','distribution/incremental_native.py')):
                assert manifest['recipes'][name]==inputs[path],path
        report['full_v05_accepted']=report['v06_dependency_satisfied']=False
        if args.scenario is None:
            checks, summaries = qualify(observations)
            report.update(checks=checks, observations=summaries)
        else:
            report['observations'] = observations
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8',newline='\n')
        print(json.dumps({'evidence': str(output), 'observations': {
            key: {k: v for k, v in value.items() if k not in ('events', 'action_states', 'asrun','messages','countdown')}
            for key, value in observations.items()},
            'checks': len(report.get('checks', {})),
            'failed_checks': {key: value.get('error', 'Dependency failed') for key, value in report.get('checks', {}).items()
                              if not value['passed']}}, indent=2))
        return bool(run.returncode or any(not value['passed'] for value in observations.values())
                    or any(not value['passed'] for value in report.get('checks', {}).values()))
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
