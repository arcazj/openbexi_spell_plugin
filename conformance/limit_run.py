"""Retain real native telemetry observations against a hash-bound DSS fixture."""
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
from limit_cases import CASES, METADATA
from installed_provenance import input_paths, verify_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-dss:v05-dta-time-obs-development')
    parser.add_argument('--case', action='append')
    parser.add_argument('--suite', choices=('limit', 'obs'), default='limit')
    args = parser.parse_args()
    all_cases, metadata = CASES, METADATA
    contracts = 'limit_contracts'
    if args.suite == 'obs':
        from obs_cases import CASES as all_cases, METADATA as metadata
        contracts = 'obs_contracts'
    cases = {k: v for k, v in all_cases.items() if args.case is None or k in args.case}
    assert cases
    output = ROOT / ('.qualification/v0.6/limit' if args.suite == 'limit' else '.qualification/v0.6/limit-obs-regression') / uuid.uuid4().hex
    output.mkdir(parents=True)
    files = [ROOT / 'conformance' / name for name in
             ('limit_cases.py', 'limit_controller.py', 'limit_contracts.py', 'limit_run.py')]
    if args.suite == 'obs':
        files += [ROOT / 'conformance' / name for name in ('obs_cases.py', 'obs_qualification_cases.py', 'obs_policy_cases.py', 'obs_contracts.py')]
    files += sorted(path for path in (ROOT / 'src/dss').rglob('*')
                    if path.is_file() and path.suffix in ('.py', '.json'))
    files += [ROOT / 'conformance/inventory.json', ROOT / 'docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    files += [ROOT / 'source_port/obs_patches.py', ROOT / 'conformance/obs.Dockerfile',
              ROOT / 'driver_plugin/src/openbexi_dss_proxy/tm.py']
    files += [ROOT / 'driver_plugin/src/openbexi_spell_dss/transport.py']
    files += [ROOT / 'driver_plugin/src/openbexi_dss_proxy/common.py']
    files += [ROOT / 'conformance/obs_combined.Dockerfile', ROOT / 'conformance/OBS.md']
    files += [ROOT / 'source_port/limit_patches.py', ROOT / 'conformance/limit_runtime.Dockerfile',
              ROOT / 'driver_plugin/src/openbexi_dss_proxy/limit_support.py']
    files += [ROOT/name for name in input_paths(ROOT)]
    files += sorted((ROOT/'driver_plugin/src').rglob('*.py'))
    inputs = {str(path.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    normalized = {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for path in files}
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    name = 'openbexi-limit-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none',
                        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
                        '--entrypoint', 'python', image, '-I', '/workspace/controller.py'], check=True, capture_output=True)
        bundle = io.BytesIO()
        with tarfile.open(fileobj=bundle, mode='w') as archive:
            targets = {
                'controller.py': (ROOT / 'conformance/limit_controller.py').read_bytes(),
                'installed_provenance.py': (ROOT / 'conformance/installed_provenance.py').read_bytes(),
                'procedure/' + contracts + '.py': (ROOT / 'conformance' / (contracts + '.py')).read_bytes(),
                'procedure/main.py': ('import ' + contracts + '\n' + contracts + '.run()\n').encode(),
                'procedure/cases.json': json.dumps(cases).encode(),
            }
            targets.update({'fixture/' + str(path.relative_to(ROOT / 'src')).replace('\\', '/'): path.read_bytes()
                            for path in files if path.is_relative_to(ROOT / 'src')})
            directories = {str(parent).replace('\\', '/') for target in targets
                           for parent in Path(target).parents if str(parent) != '.'}
            for target in sorted(directories):
                member = tarfile.TarInfo(target)
                member.type, member.mode, member.uid, member.gid = tarfile.DIRTYPE, 0o755, 10003, 10003
                archive.addfile(member)
            for target, data in targets.items():
                member = tarfile.TarInfo(target)
                member.size, member.mode, member.uid, member.gid = len(data), 0o644, 10003, 10003
                archive.addfile(member, io.BytesIO(data))
        subprocess.run(['docker', 'cp', '-a', '-', name + ':/workspace'], input=bundle.getvalue(), check=True, capture_output=True)
        run = subprocess.run(['docker', 'start', '-a', name], capture_output=True, timeout=660)
        (output / 'controller.log').write_bytes(run.stdout + run.stderr)
        subprocess.run(['docker', 'cp', name + ':/workspace/.', str(output / 'workspace')], check=True, capture_output=True)
        observations = json.loads((output / 'workspace/observations.json').read_bytes())
        check_path = output / 'workspace/procedure/checks.json'
        checks = json.loads(check_path.read_bytes()) if check_path.exists() else {}
        for key, value in checks.items():
            value.update(metadata.get(key, {}))
            observed_prompts = [prompt for prompt in observations.get('prompts', []) if prompt['check'] == key]
            value['prompts'] = observed_prompts
            if len(observed_prompts) != len(value.get('expected_prompts', [])):
                value.update(passed=False, prompt_error='Native prompt count differs from declared plan')
            if not observations['passed']:
                value.update(assertion_passed=value['passed'], passed=False,
                             runtime_error='Native run did not finish cleanly')
        assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in inputs.items())
        runtime = json.loads((output / 'workspace/runtime.json').read_bytes())
        integrated = runtime.get('integrated')
        verify_capture(integrated, inputs, normalized)
        if integrated is not None:
            driver = integrated.get('driver_composition')
            assert driver is not None, 'LIMIT requires audited installed driver composition'
            manifest = driver['manifest']
            for path, expected in manifest['python_sources'].items():
                correction = manifest['sources'].get(path)
                original = correction['original_sha256'] if correction else expected
                assert inputs['driver_plugin/src/'+path] == original, path
            assert 'limit_patches.py' in manifest['recipes']
        if '/opt/obs-conformance-patch/obs_patches.py' in runtime['installed']:
            assert runtime['installed']['/opt/obs-conformance-patch/obs_patches.py'] == inputs['source_port/obs_patches.py']
            for path in ('openbexi_dss_proxy/tm.py', 'openbexi_dss_proxy/common.py', 'openbexi_spell_dss/transport.py'):
                modified = runtime['manifests'].get('limit-patch', {}).get(path)
                expected = modified['sha256'] if modified else inputs['driver_plugin/src/' + path]
                if modified:
                    assert modified['preimage_sha256'] == inputs['driver_plugin/src/' + path]
                assert runtime['installed']['/usr/local/lib/python3.13/site-packages/' + path] == expected, path
        if 'limit-patch' in runtime['manifests']:
            assert runtime['installed']['/opt/limit-patch/limit_patches.py'] == inputs['source_port/limit_patches.py']
            assert runtime['installed']['/opt/limit-patch/limit_runtime.Dockerfile'] == inputs['conformance/limit_runtime.Dockerfile']
            assert runtime['installed']['/usr/local/lib/python3.13/site-packages/openbexi_dss_proxy/limit_support.py'] == inputs['driver_plugin/src/openbexi_dss_proxy/limit_support.py']
        report = dict(suite=args.suite, runtime_image=image, inputs=inputs, lf_normalized_inputs=normalized, checks=checks, observations=observations,
                      runtime_sources=runtime, controller_exit_code=run.returncode,
                      full_v05_accepted=False, v06_dependency_satisfied=False)
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(dict(output=str(output), controller=run.returncode, status=observations.get('status'),
                              checks=len(checks), failed={key: row for key, row in checks.items() if not row['passed']}), indent=2))
        return bool(run.returncode or not observations['passed'] or len(checks) != len(cases)
                    or any(not value['passed'] for value in checks.values()))
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
