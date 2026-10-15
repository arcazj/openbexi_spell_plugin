"""Retain native comparison observations without claiming release acceptance."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from installed_provenance import input_paths, verify_capture
from legacy_compare_cases import CASES, INVALID

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    output = ROOT / '.qualification/legacy-compare' / uuid.uuid4().hex
    output.mkdir(parents=True)
    names = [*input_paths(ROOT), 'conformance/legacy_compare_cases.py',
        'conformance/legacy_compare_controller.py', 'conformance/legacy_compare_provenance.py',
        'conformance/run_legacy_compare.py', 'source_port/legacy_compare_syntax.py',
        'conformance/legacy_compare_build.py', 'conformance/legacy_compare_install.py',
        'conformance/legacy_compare.Dockerfile', 'conformance/legacy_compare.Dockerfile.dockerignore',
        'distribution/incremental_native.py', 'docs/reference/SPELL2.6.10-src.zip',
        'docs/reference/SPELL - Language Reference - 2.4.4.pdf', 'conformance/inventory.json']
    inputs = {name: sha(ROOT / name) for name in names}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name = 'openbexi-legacy-compare-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','256','--entrypoint','python',image,
            '-I','/workspace/legacy_compare_controller.py'],check=True,capture_output=True)
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for file in ('legacy_compare_cases.py','legacy_compare_controller.py',
                         'legacy_compare_provenance.py','installed_provenance.py'):
                content = (ROOT/'conformance'/file).read_bytes()
                info = tarfile.TarInfo(file)
                info.size, info.uid, info.gid, info.mode = len(content),10003,10003,0o644
                archive.addfile(info,io.BytesIO(content))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=stream.getvalue(),check=True,capture_output=True)
        run = subprocess.run(['docker','start','-a',name],capture_output=True,timeout=660)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        content = subprocess.check_output(['docker','cp',name+':/workspace/.','-'],timeout=30)
        (output/'workspace.tar').write_bytes(content)
        with tarfile.open(fileobj=io.BytesIO(content)) as archive:
            members = {m.name.removeprefix('./'):m for m in archive if m.isfile()}
            checks = json.loads(archive.extractfile(members['checks.json']).read())
            runtime = json.loads(archive.extractfile(members['runtime.json']).read())
        assert set(checks) == set(CASES) | set(INVALID)
        assert all(sha(ROOT/path)==digest for path,digest in inputs.items())
        verify_capture(runtime['integrated'],inputs)
        if runtime['overlay']:
            for file,digest in runtime['overlay']['recipes'].items():
                prefix = 'source_port/' if file in ('legacy_compare_patches.py','legacy_compare_syntax.py') else 'distribution/' if file=='incremental_native.py' else 'conformance/'
                assert sha(ROOT/prefix/file)==digest, file
        passed = run.returncode == 0 and all(r['passed'] is True for r in checks.values())
        report = dict(passed=passed,runtime_image=image,inputs=inputs,checks=checks,runtime_sources=runtime,
            controller_exit_code=run.returncode,qualified_contracts=[],full_v05_accepted=False,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({'output':str(output),'passed':passed,'checks':len(checks),
            'failures':{k:r.get('error') for k,r in checks.items() if not r['passed']}},indent=2))
        return 0 if passed else 1
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
