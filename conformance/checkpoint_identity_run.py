"""Retain actual native IPC checkpoint source-identity and recovery controls."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from installed_provenance import input_paths
from checkpoint_identity_provenance import qualification_identity


def checks_passed(checks, options):
    expected = {mode+':'+case for mode in options['modes'] for case in options['cases']}
    return bool(expected) and set(checks) == expected and all(
        row.get('passed') is True and not any(row.get(key) for key in
        ('error', 'cleanup_error', 'extra_cleanup_error', 'drain_error', 'sanitizer_failure'))
        for row in checks.values())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--recovery',action='store_true')
    parser.add_argument('--case',action='append')
    parser.add_argument('--mode',action='append')
    args=parser.parse_args()
    options=dict(cases=args.case or ['module-error','named-error','nested-error','user-action-error'],
        modes=args.mode or ['ON_LINE','ON_STEP'],kind='recovery' if args.recovery else 'error-ipc')
    controller='checkpoint_identity_ipc.py'
    if args.recovery:
        controller='checkpoint_identity_recovery.py'
        options['cases']=args.case or ['normal','two-instances','kill-resume','changed-source','missing-wsp','empty-wsp',
            'corrupt-wsp','missing-asrun','empty-asrun','invalid-path','partial-stem']
    output=ROOT/'.qualification/v0.6/checkpoint-identity'/uuid.uuid4().hex
    output.mkdir(parents=True)
    files=[ROOT/'conformance'/name for name in ('checkpoint_identity_ipc.py','checkpoint_identity_recovery.py','checkpoint_identity_run.py',
        'scdb_provenance.py','installed_provenance.py','checkpoint_identity_provenance.py')]
    files += [ROOT/name for name in ('source_port/checkpoint_identity_patches.py','source_port/checkpoint_context_patches.py','source_port/checkpoint_error_patches.py',
        'conformance/checkpoint_identity_build.py','conformance/checkpoint_identity_install.py',
        'conformance/checkpoint_identity.Dockerfile','conformance/checkpoint_identity.Dockerfile.dockerignore',
        'distribution/incremental_native.py','host_runtime/python/native.py')]
    files=list(dict.fromkeys([*files,*(ROOT/name for name in input_paths(ROOT))]))
    files += [ROOT / name for name in ('conformance/ipc_mailbox_provenance.py',
        'conformance/ipc_mailbox_build.py', 'conformance/ipc_mailbox_race.cpp',
        'conformance/ipc_mailbox_install.py', 'conformance/ipc_mailbox.Dockerfile')]
    inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    normalized={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files}
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-checkpoint-identity-'+uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','256','--entrypoint','python',image,
            '-I','/workspace/'+controller],check=True,capture_output=True)
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            entries=[(p.name,p.read_bytes()) for p in files if p.suffix=='.py' and p.parent==ROOT/'conformance']+[('input.json',json.dumps(options).encode())]
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
        if 'mailbox_overlay' in runtime:
            from ipc_mailbox_provenance import qualification_identity as mailbox_identity
            mailbox_identity(runtime, inputs, normalized)
        elif 'identity_overlay' in runtime:
            recipes=runtime['identity_overlay']['recipes']
            for name,path in [('checkpoint_identity_patches.py','source_port/checkpoint_identity_patches.py'),
                ('checkpoint_error_patches.py','source_port/checkpoint_error_patches.py'),
                ('checkpoint_context_patches.py','source_port/checkpoint_context_patches.py'),
                ('checkpoint_identity_build.py','conformance/checkpoint_identity_build.py'),
                ('incremental_native.py','distribution/incremental_native.py')]:
                assert recipes[name]==inputs[path],name
        elif runtime.get('profile'):
            qualification_identity(runtime,inputs,normalized)
        assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in inputs.items())
        passed = run.returncode == 0 and checks_passed(checks, options)
        report=dict(passed=passed,runtime_image=image,inputs=inputs,lf_normalized_inputs=normalized,options=options,checks=checks,runtime_sources=runtime,
            controller_exit_code=run.returncode,full_v05_accepted=False,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(output=str(output),checks=len(checks),failed=[k for k,v in checks.items() if not v['passed']]),indent=2))
        return not passed
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__=='__main__':
    raise SystemExit(main())
