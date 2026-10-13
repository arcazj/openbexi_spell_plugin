"""Retain native SCDB policy checks and independent file/provenance evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid
from scdb_cases import CASES
from installed_provenance import input_paths, verify_capture

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--case',action='append')
    args=parser.parse_args()
    cases={name:row for name,row in CASES.items() if not args.case or name in args.case}
    assert cases
    output=ROOT/'.qualification/v0.6/scdb'/uuid.uuid4().hex
    output.mkdir(parents=True)
    files=list((ROOT/'conformance').glob('scdb*'))+[ROOT/n for n in input_paths(ROOT)]
    files += [ROOT/'conformance/inventory.json',ROOT/'docs/reference/SPELL2.6.10-src.zip',ROOT/'docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-scdb-'+uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','256','--entrypoint','python',image,
            '-I','/workspace/scdb_controller.py'],check=True,capture_output=True)
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            entries=[(p.name,p.read_bytes()) for p in files if p.parent==ROOT/'conformance' and p.suffix=='.py']
            entries.append(('cases.json',json.dumps(cases).encode()))
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
        verify_capture(runtime['baseline'],inputs)
        assert runtime['import_recipe_sha256']==inputs['source_port/database_import_patches.py']
        if runtime['scdb']:
            assert runtime['scdb']['recipe_sha256']==inputs['source_port/scdb_patches.py']
        assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in inputs.items())
        report=dict(runtime_image=image,inputs=inputs,checks=checks,runtime_sources=runtime,
            controller_exit_code=run.returncode,full_v05_accepted=False,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        failed={k:v.get('error') for k,v in checks.items() if not v['passed']}
        print(json.dumps(dict(output=str(output),checks=len(checks),failed=failed),indent=2))
        return bool(run.returncode or set(checks)!=set(cases)|{'checkpoint:on_line','checkpoint:on_step'} or failed)
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__=='__main__':
    raise SystemExit(main())
