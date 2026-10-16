"""Retain native telemetry deadline and source-failure cases; no qualification is inferred."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from send_complete_cases import CASES
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--case',action='append',choices=list(CASES))
    args=parser.parse_args()
    cases={name:spec for name,spec in CASES.items() if args.case is None or name in args.case}
    token=uuid.uuid4().hex
    output=ROOT/'.qualification/send-complete'/token
    output.mkdir(parents=True)
    names=['conformance/send_complete_provenance.py','source_port/send_complete_patches.py','conformance/send_complete.Dockerfile','conformance/send_complete.Dockerfile.dockerignore','conformance/memory_native_cases.py','conformance/send_complete_cases.py','conformance/send_complete_controller.py',
           'conformance/run_send_complete.py','conformance/inventory.json',
           'conformance/telemetry_surface_cases.py','conformance/telemetry_features_provenance.py',
           'conformance/telemetry_features.Dockerfile','conformance/telemetry_features.Dockerfile.dockerignore',
           'conformance/TELEMETRY_DEADLINE_PROFILE.md','driver_plugin/src/openbexi_spell_dss/limit_files/normal.json',
           'conformance/TELEMETRY_BOUNDARY_REVIEW.md','tests/test_telemetry_comparison_boundaries.py',
           'docs/reference/SPELL - Language Reference - 2.4.4.pdf',
           'docs/reference/SPELL2.6.10-src.zip','conformance/TELEMETRY_SURFACE_BASELINE.md',*input_paths(ROOT),
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'src/dss').rglob('*')) if p.is_file() and p.suffix in ('.py','.json')],
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'host_runtime/python').glob('*.py'))]]
    inputs={n:sha(ROOT/n) for n in names}
    for n in inputs:
        target=output/'inputs'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/n).read_bytes())
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-telemetry-features-'+token
    created=False
    exported=False
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-u','/workspace/send_complete_controller.py'],check=True,capture_output=True)
        created=True
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            content=json.dumps(list(cases)).encode()
            item=tarfile.TarInfo('selected-cases.json')
            item.size,item.mode,item.uid,item.gid=len(content),0o644,10003,10003
            bundle.addfile(item,io.BytesIO(content))
            for source in ('send_complete_provenance.py','memory_native_cases.py','send_complete_cases.py','send_complete_controller.py','installed_provenance.py','telemetry_surface_cases.py','telemetry_features_provenance.py'):
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
        assert runtime['profile'] in ('fresh-composed-limit-telemetry-send-complete-overlays/1',)
        host=json.loads((output/'workspace/host-inputs.json').read_bytes())
        assert host=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
        assert all(sha(ROOT/n)==v for n,v in inputs.items())
        report=dict(passed=exit_code==0 and set(checks)==set(cases) and all(r['passed'] for r in checks.values()),
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
