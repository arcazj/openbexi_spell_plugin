"""Retain native StartProc argument controls on a fresh installed image."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from child_arguments_cases import CASES
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    token=uuid.uuid4().hex
    output=ROOT/'.qualification/child-arguments'/token
    output.mkdir(parents=True)
    names=['conformance/child_arguments_cases.py','conformance/child_arguments_controller.py',
           'conformance/run_child_arguments.py','conformance/inventory.json',
           'docs/reference/SPELL - Language Reference - 2.4.4.pdf',
           'docs/reference/SPELL2.6.10-src.zip',*input_paths(ROOT),
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'host_runtime/python').glob('*.py'))]]
    inputs={n:sha(ROOT/n) for n in names}
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-child-arguments-'+token
    created=False
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-u','/workspace/child_arguments_controller.py'],check=True,capture_output=True)
        created=True
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            for source in ('child_arguments_cases.py','child_arguments_controller.py','installed_provenance.py'):
                content=(ROOT/'conformance'/source).read_bytes()
                item=tarfile.TarInfo(source)
                item.size,item.mode,item.uid,item.gid=len(content),0o644,10003,10003
                bundle.addfile(item,io.BytesIO(content))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        timed_out=False
        try:
            run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=300)
            exit_code=run.returncode
        except subprocess.TimeoutExpired:
            timed_out,exit_code=True,-1
            subprocess.run(['docker','kill',name],check=True,capture_output=True,timeout=20)
        logs=subprocess.run(['docker','logs',name],check=True,capture_output=True,timeout=20)
        (output/'controller.log').write_bytes(logs.stdout+logs.stderr)
        subprocess.run(['docker','cp',name+':/workspace/.',str(output/'workspace')],check=True,capture_output=True)
        checks=json.loads((output/'workspace/checks.json').read_bytes())
        runtime=json.loads((output/'workspace/runtime.json').read_bytes())
        assert runtime is not None
        verify_capture(runtime,inputs)
        host=json.loads((output/'workspace/host-inputs.json').read_bytes())
        assert host=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
        assert all(sha(ROOT/n)==v for n,v in inputs.items())
        report=dict(passed=exit_code==0 and set(checks)==set(CASES) and all(r['passed'] for r in checks.values()),
            runtime_image=image,inputs=inputs,checks=checks,runtime_sources={'integrated':runtime},
            host_inputs=host,controller_exit_code=exit_code,timed_out=timed_out,
            full_v05_accepted=False,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({'output':str(output),'passed':report['passed'],
            'failures':{k:v.get('error') for k,v in checks.items() if not v['passed']}}))
        return not report['passed']
    finally:
        if created:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__=='__main__':
    raise SystemExit(main())
