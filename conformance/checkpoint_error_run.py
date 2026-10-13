"""Retain isolated checkpoint controls without changing the qualified SCDB recipe."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--case',action='append')
    parser.add_argument('--ipc',action='store_true')
    parser.add_argument('--mode',action='append')
    parser.add_argument('--execution',action='append')
    args=parser.parse_args()
    options=dict(cases=args.case or ['direct-valueerror','lambda-valueerror','named-valueerror',
        'lambda-keyerror','lambda-success','lambda-original-driver'],
        modes=args.mode or ['ON_LINE','ON_STEP'],executions=args.execution or ['fresh','resume'])
    if args.ipc:
        options['cases']=args.case or ['module-error','named-error','nested-error','user-action-error']
    controller='checkpoint_error_ipc.py' if args.ipc else 'checkpoint_error_controller.py'
    output=ROOT/'.qualification/v0.6/checkpoint-error'/uuid.uuid4().hex
    output.mkdir(parents=True)
    files=[ROOT/'conformance'/name for name in ('checkpoint_error_controller.py','checkpoint_error_ipc.py','checkpoint_error_run.py',
        'scdb_provenance.py','installed_provenance.py','checkpoint_error_provenance.py')]
    files += [ROOT/name for name in ('source_port/checkpoint_error_patches.py',
        'conformance/checkpoint_error_build.py','conformance/checkpoint_error_install.py',
        'conformance/checkpoint_error.Dockerfile','conformance/checkpoint_error.Dockerfile.dockerignore',
        'distribution/incremental_native.py')]
    inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-checkpoint-error-'+uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','128','--entrypoint','python',image,
            '-I','/workspace/'+controller],check=True,capture_output=True)
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            entries=[(p.name,p.read_bytes()) for p in files if p.suffix=='.py']+[('input.json',json.dumps(options).encode())]
            for target,data in entries:
                item=tarfile.TarInfo(target)
                item.size,item.uid,item.gid,item.mode=len(data),10003,10003,0o644
                bundle.addfile(item,io.BytesIO(data))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=1200)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        raw=subprocess.check_output(['docker','cp',name+':/workspace/.','-'],timeout=30)
        (output/'workspace.tar').write_bytes(raw)
        with tarfile.open(fileobj=io.BytesIO(raw)) as bundle:
            members={p.name.removeprefix('./'):p for p in bundle.getmembers() if p.isfile()}
            checks=json.loads(bundle.extractfile(members['checks.json']).read())
            runtime=json.loads(bundle.extractfile(members['runtime.json']).read())
        if 'checkpoint_overlay' in runtime:
            recipes=runtime['checkpoint_overlay']['recipes']
            for name,path in [('checkpoint_error_patches.py','source_port/checkpoint_error_patches.py'),
                ('checkpoint_error_build.py','conformance/checkpoint_error_build.py'),
                ('incremental_native.py','distribution/incremental_native.py')]:
                assert recipes[name]==inputs[path],name
        assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in inputs.items())
        report=dict(runtime_image=image,inputs=inputs,options=options,checks=checks,runtime_sources=runtime,
            controller_exit_code=run.returncode,full_v05_accepted=False,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(output=str(output),checks=len(checks),failed=[k for k,v in checks.items() if not v['passed']]),indent=2))
        return bool(run.returncode)
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__=='__main__':
    raise SystemExit(main())
