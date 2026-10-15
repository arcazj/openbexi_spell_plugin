"""Retain native rng observations against the persistent GENERIC ground DB."""
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
from rng_cases import CASES, METADATA
from installed_provenance import input_paths, verify_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--case', action='append')
    parser.add_argument('--catalog-only', action='store_true',
                        help='Run the eight catalog controls, excluding legacy activity observations')
    args = parser.parse_args()
    if args.catalog_only:
        assert args.case is None, 'Select catalog-only or explicit cases'
        args.case=[key for key in CASES if key.startswith(('baseband-names:','antenna-names:'))]
    assert args.case is None or set(args.case)<=set(CASES), 'Unknown ranging case'
    cases = {k: v for k, v in CASES.items() if args.case is None or k in args.case}
    assert cases
    output = ROOT / '.qualification/v0.5/rng' / uuid.uuid4().hex
    output.mkdir(parents=True)
    files=[ROOT/'conformance'/name for name in ('rng_cases.py','rng_controller.py','rng_contracts.py','run_rng.py','rng_provenance.py','RNG.md')]
    files += sorted(path for path in (ROOT/'src/dss').rglob('*') if path.is_file() and path.suffix in ('.py','.json'))
    files += [ROOT/name for name in ('conformance/inventory.json','docs/reference/SPELL - Language Reference - 2.4.4.pdf','docs/reference/SPELL2.6.10-src.zip','host_runtime/python/native.py')]
    files += [ROOT/name for name in input_paths(ROOT)]
    files += [path for path in (ROOT/'source_port/rng_patches.py',ROOT/'conformance/rng.Dockerfile',ROOT/'conformance/rng.Dockerfile.dockerignore') if path.exists()]
    files=list(dict.fromkeys(files))
    inputs={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    normalized={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for path in files}
    for path in files:
        target=output/'inputs'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(path.read_bytes())
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    name = 'openbexi-rng-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none',
                        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
                        '--entrypoint', 'python', image, '-I', '/workspace/controller.py'], check=True, capture_output=True)
        bundle = io.BytesIO()
        with tarfile.open(fileobj=bundle, mode='w') as archive:
            targets = {
                'controller.py': (ROOT / 'conformance/rng_controller.py').read_bytes(),
                'installed_provenance.py': (ROOT / 'conformance/installed_provenance.py').read_bytes(),
                'rng_provenance.py': (ROOT/'conformance/rng_provenance.py').read_bytes(),
                'procedure/rng_contracts.py': (ROOT / 'conformance/rng_contracts.py').read_bytes(),
                'procedure/main.py': b'import rng_contracts\nrng_contracts.run()\n',
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
            value.update(METADATA.get(key, {}))
            observed_prompts = [prompt for prompt in observations.get('prompts', []) if prompt['check'] == key]
            value['prompts'] = observed_prompts
            if len(observed_prompts) != len(value.get('expected_prompts', [])):
                value.update(passed=False, prompt_error='Native prompt count differs from declared plan')
            if not observations['passed']:
                value.update(assertion_passed=value['passed'], passed=False,
                             runtime_error='Native run did not finish cleanly')
        assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in inputs.items())
        runtime = json.loads((output / 'workspace/runtime.json').read_bytes())
        verify_capture(runtime.get('integrated'), inputs, normalized)
        assert runtime['integrated'], 'Original integrated native provenance is required'
        driver=runtime['integrated']['driver_composition']['manifest']['python_sources']
        for path in ('openbexi_dss_proxy/ranging.py','openbexi_spell_dss/ground.py','openbexi_spell_dss/journal.py','openbexi_spell_dss/rpc.py'):
            row=(runtime.get('overlay') or {}).get('manifest',{}).get(path)
            assert runtime['installed'][path]==(row['sha256'] if row else driver[path]),path
        if runtime['overlay']:
            for name in ('rng_patches.py',):
                assert runtime['overlay']['files'][name] in (inputs['source_port/'+name],normalized['source_port/'+name])
            for name in ('rng_provenance.py','rng.Dockerfile'):
                assert runtime['overlay']['files'][name] in (inputs['conformance/'+name],normalized['conformance/'+name])
        report = dict(runtime_image=image, inputs=inputs, lf_normalized_inputs=normalized, checks=checks, observations=observations,
                      selection='catalog' if args.catalog_only else ('explicit' if args.case else 'diagnostic-all'),
                      runtime_sources=runtime, controller_exit_code=run.returncode,
                      full_v05_accepted=False, v06_dependency_satisfied=False)
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(dict(output=str(output), controller=run.returncode, status=observations.get('status'),
                              checks=len(checks), failed={key: row.get('error',row.get('prompt_error')) for key, row in checks.items() if not row['passed']}), indent=2))
        return bool(run.returncode or not observations['passed'] or len(checks) != len(cases)
                    or any(not value['passed'] for value in checks.values()))
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
