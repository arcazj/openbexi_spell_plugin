"""Retain eight native command counterexample probes; no qualification is inferred."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from command_catalog_cases import CASES
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--composed',action='store_true')
    parser.add_argument('--case',action='append',choices=list(CASES))
    args=parser.parse_args()
    cases={name:spec for name,spec in CASES.items() if args.case is None or name in args.case}
    token=uuid.uuid4().hex
    output=ROOT/'.qualification/command-catalog'/token
    output.mkdir(parents=True)
    names=['conformance/command_catalog_cases.py','conformance/command_catalog_controller.py','conformance/clock_step.py',
           'conformance/run_command_catalog.py','conformance/inventory.json','conformance/command_catalog_provenance.py','conformance/command_catalog.Dockerfile','conformance/command_catalog.Dockerfile.dockerignore',
           'docs/reference/SPELL - Language Reference - 2.4.4.pdf',
           'docs/reference/SPELL2.6.10-src.zip','conformance/COMMAND_FEATURE_BASELINE.md',*input_paths(ROOT),
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'src/dss').rglob('*')) if p.is_file() and p.suffix in ('.py','.json')],
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'host_runtime/python').glob('*.py'))]]
    inputs={n:sha(ROOT/n) for n in names}
    for n in inputs:
        p=output/'inputs'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/n).read_bytes())
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-command-catalog-'+token
    created=False
    exported=False
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--env','OPENBEXI_CONFORMANCE_COMPOSED='+str(int(args.composed)),
            '--entrypoint','python',image,'-u','/workspace/command_catalog_controller.py'],check=True,capture_output=True)
        created=True
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            content=json.dumps(list(cases)).encode()
            item=tarfile.TarInfo('selected-cases.json')
            item.size,item.mode,item.uid,item.gid=len(content),0o644,10003,10003
            bundle.addfile(item,io.BytesIO(content))
            for source in ('command_catalog_cases.py','command_catalog_controller.py','clock_step.py','installed_provenance.py','command_catalog_provenance.py'):
                content=(ROOT/'conformance'/source).read_bytes()
                item=tarfile.TarInfo(source)
                item.size,item.mode,item.uid,item.gid=len(content),0o644,10003,10003
                bundle.addfile(item,io.BytesIO(content))
            for path in sorted((ROOT/'src/dss').rglob('*')):
                if not path.is_file() or path.suffix not in ('.py','.json'): continue
                content=path.read_bytes()
                item=tarfile.TarInfo('fixture/'+path.relative_to(ROOT/'src').as_posix())
                item.size,item.mode,item.uid,item.gid=len(content),0o644,10003,10003
                bundle.addfile(item,io.BytesIO(content))

        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        timed_out=False
        try:
            run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=1500)
            exit_code=run.returncode
        except subprocess.TimeoutExpired:
            timed_out,exit_code=True,-1
            subprocess.run(['docker','kill',name],check=True,capture_output=True,timeout=20)
        logs=subprocess.run(['docker','logs',name],check=True,capture_output=True,timeout=20)
        (output/'controller.log').write_bytes(logs.stdout+logs.stderr)
        subprocess.run(['docker','cp',name+':/workspace/.',str(output/'workspace')],check=True,capture_output=True)
        exported=True
        checks=json.loads((output/'workspace/checks.json').read_bytes())
        runtime=json.loads((output/'workspace/runtime.json').read_bytes())
        assert runtime is not None
        verify_capture(runtime['integrated'],inputs)
        assert runtime['profile']==('fresh-composed-display-command-wheel/1' if args.composed else 'fresh-wheel-plus-display-command-and-catalog-overlays/1')
        host=json.loads((output/'workspace/host-inputs.json').read_bytes())
        assert host=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
        assert all(sha(ROOT/n)==v for n,v in inputs.items())
        report=dict(composed=args.composed,passed=exit_code==0 and set(checks)==set(cases) and all(r['passed'] for r in checks.values()),
            runtime_image=image,inputs=inputs,checks=checks,runtime_sources=runtime,
            host_inputs=host,controller_exit_code=exit_code,timed_out=timed_out,
            artifacts={p.relative_to(output/'workspace').as_posix():sha(p) for p in (output/'workspace').rglob('*') if p.is_file()},
            diagnostic_only=True,qualified_contracts=[],full_v05_accepted=False,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({'output':str(output),'passed':report['passed'],
            'failures':{k:v.get('error') for k,v in checks.items() if not v['passed']}}))
        return not report['passed']
    finally:
        if created and exported:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)
        elif created:
            print('Retained container after incomplete export: '+name,flush=True)


if __name__=='__main__':
    raise SystemExit(main())
