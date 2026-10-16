"""Retain the complete native display suite and exact diagnostic source provenance."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from display_cases import CASES
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--case', action='append', choices=list(CASES))
    args = parser.parse_args()
    cases = {key: value for key,value in CASES.items() if args.case is None or key in args.case}
    output = ROOT / '.qualification/gcs-display' / uuid.uuid4().hex
    output.mkdir(parents=True)
    print('Evidence: ' + str(output), flush=True)
    files = ['conformance/' + name for name in ('display_cases.py', 'display_contracts.py',
        'display_controller.py', 'display_provenance.py', 'display.Dockerfile',
        'display.Dockerfile.dockerignore', 'run_display.py', 'GCS_DISPLAY_IMPLEMENTATION.md', 'inventory.json')]
    files += ['docs/reference/SPELL - Language Reference - 2.4.4.pdf', 'docs/reference/SPELL2.6.10-src.zip',
              *input_paths(ROOT)]
    files += [path.relative_to(ROOT).as_posix() for path in (ROOT / 'src/dss').rglob('*')
              if path.is_file() and path.suffix in ('.py', '.json')]
    files += [path.relative_to(ROOT).as_posix() for path in (ROOT / 'host_runtime/python').glob('*.py')]
    inputs = {name: sha(ROOT / name) for name in files}
    for name in inputs:
        target = output / 'inputs' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    name = 'openbexi-gcs-display-' + uuid.uuid4().hex
    created = False
    report = dict(passed=False, runtime_image=image, inputs=inputs, diagnostic_only=True,
                  qualified_contracts=[], full_v05_accepted=False, full_v06_accepted=False)
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
            '--entrypoint', 'python', image, '-I', '/workspace/display_controller.py'], check=True, capture_output=True)
        created = True
        targets = {filename: (ROOT / 'conformance' / filename).read_bytes() for filename in
                   ('display_controller.py', 'display_provenance.py', 'installed_provenance.py')}
        targets.update({'procedure/main.py': b'import display_contracts\ndisplay_contracts.run()\n',
                        'procedure/display_contracts.py': (ROOT / 'conformance/display_contracts.py').read_bytes(),
                        'procedure/cases.json': json.dumps(cases).encode()})
        targets.update({'fixture/' + name.removeprefix('src/'): (ROOT / name).read_bytes()
                        for name in inputs if name.startswith('src/dss/')})
        bundle = io.BytesIO()
        with tarfile.open(fileobj=bundle, mode='w') as archive:
            directories = {str(parent).replace('\\', '/') for target in targets
                           for parent in Path(target).parents if str(parent) != '.'}
            for target in sorted(directories):
                item = tarfile.TarInfo(target)
                item.type, item.mode, item.uid, item.gid = tarfile.DIRTYPE, 0o755, 10003, 10003
                archive.addfile(item)
            for target, content in targets.items():
                item = tarfile.TarInfo(target)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                archive.addfile(item, io.BytesIO(content))
        subprocess.run(['docker', 'cp', '-a', '-', name + ':/workspace'], input=bundle.getvalue(), check=True, capture_output=True)
        try:
            run = subprocess.run(['docker', 'start', '-a', name], capture_output=True, timeout=1260)
            report['controller_exit_code'] = run.returncode
            (output / 'controller.log').write_bytes(run.stdout + run.stderr)
        except subprocess.TimeoutExpired:
            report.update(controller_exit_code=-1, timed_out=True)
            subprocess.run(['docker', 'kill', name], check=True, capture_output=True, timeout=20)
            logs = subprocess.run(['docker', 'logs', name], check=True, capture_output=True, timeout=20)
            (output / 'controller.log').write_bytes(logs.stdout + logs.stderr)
        subprocess.run(['docker', 'cp', name + ':/workspace/.', str(output / 'workspace')], check=True, capture_output=True)
        runtime = json.loads((output / 'workspace/runtime.json').read_bytes())
        verify_capture(runtime['integrated'], inputs)
        assert runtime['profile'] == 'fresh-wheel-plus-declared-display-overlay/1'
        overlay = runtime['overlay']
        assert set(overlay['manifest']) == {
            'spell/lang/functions.py', 'spell/lang/constants.py', 'spell/lang/modifiers.py',
            'spell/lang/helpers/tskhelper.py', 'spell/lib/adapter/task.py',
            'openbexi_dss_proxy/task.py', 'openbexi_spell_dss/ground.py',
            'openbexi_spell_dss/rpc.py', 'openbexi_spell_dss/journal.py'}
        for item in ('display_provenance.py', 'display.Dockerfile', 'installed_provenance.py'):
            assert overlay['files'][item] == inputs['conformance/' + item]
        assert overlay['files']['display_patches.py'] == inputs['source_port/display_patches.py']
        assert set(overlay['added_sources']) == {'openbexi_spell_dss/displays.py', 'openbexi_spell_dss/display_viewer.py'}
        for item, value in overlay['added_sources'].items():
            assert value == inputs['driver_plugin/src/' + item] == runtime['installed'][item]
            assert overlay['files']['modules/' + item] == value
        host = json.loads((output / 'workspace/host-inputs.json').read_bytes())
        assert host == {path.name: sha(path) for path in (ROOT / 'host_runtime/python').glob('*.py')}
        assert all(sha(ROOT / item) == value for item,value in inputs.items())
        checks = json.loads((output / 'workspace/procedure/checks.json').read_bytes())
        controller = json.loads((output / 'workspace/controller-result.json').read_bytes())
        assert set(checks) == set(cases)
        for item, spec in cases.items():
            assert all(checks[item][key] == value for key,value in spec.items())
        report.update(runtime_sources=runtime, host_inputs=host, checks=checks, controller=controller,
            artifacts={path.relative_to(output / 'workspace').as_posix(): sha(path)
                       for path in (output / 'workspace').rglob('*') if path.is_file()})
        report['passed'] = report['controller_exit_code'] == 0 and controller['passed'] and all(row['passed'] for row in checks.values())
    except Exception as error:
        import traceback
        report['error'] = traceback.format_exc()
    finally:
        if created:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)
        (output / 'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps(dict(output=str(output), passed=report['passed'], error=report.get('error'),
            failures={key: row.get('error') for key,row in report.get('checks', {}).items() if not row['passed']})), flush=True)
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
