"""Retain repeated native listener discovery and startup observations."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from installed_provenance import input_paths
from checkpoint_identity_provenance import qualification_identity as installed_identity
from context_snapshot_provenance import qualification_identity as overlay_identity, RECIPES

ROOT = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--repeat', type=int, default=40)
    args = parser.parse_args()
    assert 1 <= args.repeat <= 100
    output = ROOT / '.qualification/context-snapshot-startup' / uuid.uuid4().hex
    output.mkdir(parents=True)
    scripts = ('context_snapshot_startup.py','context_snapshot_provenance.py',
               'checkpoint_identity_provenance.py','installed_provenance.py')
    names = list(dict.fromkeys([*input_paths(ROOT), *RECIPES.values(),
        *('conformance/' + name for name in scripts), 'conformance/run_context_snapshot.py',
        'host_runtime/python/native.py', 'conformance/context_snapshot_install.py',
        'conformance/context_snapshot.Dockerfile', 'conformance/context_snapshot.Dockerfile.dockerignore',
        'docs/reference/SPELL2.6.10-src.zip']))
    inputs = {name:sha(ROOT / name) for name in names}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'], text=True).strip()
    name = 'openbexi-context-snapshot-' + uuid.uuid4().hex
    options = dict(repeat=args.repeat)
    print('Evidence: ' + str(output), flush=True)
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','256','--entrypoint','python',image,
            '-I','/workspace/context_snapshot_startup.py'], check=True, capture_output=True)
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            files = {name:(ROOT / 'conformance' / name).read_bytes() for name in scripts}
            files['input.json'] = json.dumps(options).encode()
            for filename, data in files.items():
                item = tarfile.TarInfo(filename)
                item.size, item.uid, item.gid, item.mode = len(data),10003,10003,0o644
                archive.addfile(item, io.BytesIO(data))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'], input=stream.getvalue(), check=True, capture_output=True)
        run = subprocess.run(['docker','start','-a',name], capture_output=True, timeout=30 * args.repeat + 60)
        (output / 'controller.log').write_bytes(run.stdout + run.stderr)
        raw = subprocess.check_output(['docker','cp',name+':/workspace/.','-'], timeout=30)
        (output / 'workspace.tar').write_bytes(raw)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            members = {item.name.removeprefix('./'):item for item in archive if item.isfile()}
            read = lambda filename: json.loads(archive.extractfile(members[filename]).read())
            checks, runtime = read('checks.json'), read('runtime.json')
        assert all(sha(ROOT / path) == digest for path,digest in inputs.items())
        verifier = overlay_identity if 'context_snapshot_overlay' in runtime else installed_identity
        verifier(runtime, inputs)
        passed = run.returncode == 0 and set(checks) == {'startup-' + str(n).zfill(3) for n in range(args.repeat)}
        passed = passed and all(row['passed'] and not row.get('error') and not row.get('cleanup_error') for row in checks.values())
        report = dict(passed=passed, runtime_image=image, inputs=inputs, checks=checks,
            runtime_sources=runtime, options=options, controller_exit_code=run.returncode,
            qualified_contracts=[], full_v05_accepted=False, full_v06_accepted=False)
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(dict(output=str(output), passed=passed, checks=len(checks),
            failed={k:row.get('error',row.get('cleanup_error')) for k,row in checks.items() if not row['passed']})))
        return not passed
    finally:
        subprocess.run(['docker','rm','-f',name], capture_output=True, timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
