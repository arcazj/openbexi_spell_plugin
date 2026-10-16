"""Retain native user-database persistence and source identities."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from database_format_cases import CASES
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    output=ROOT / '.qualification/database-formats' / uuid.uuid4().hex
    output.mkdir(parents=True)
    names=['conformance/database_format_cases.py','conformance/database_format_controller.py','conformance/run_database_formats.py','host_runtime/python/native.py','conformance/inventory.json','docs/reference/SPELL2.6.10-src.zip','docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    names += input_paths(ROOT)
    inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    normalized={name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in names}
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-database-formats-'+uuid.uuid4().hex
    exported=False
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
                        '--entrypoint','python',image,'-I','/workspace/controller.py'],check=True,capture_output=True)
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            for target,data in [('controller.py',(ROOT/'conformance/database_format_controller.py').read_bytes()),('cases.json',json.dumps(CASES).encode()),('installed_provenance.py',(ROOT/'conformance/installed_provenance.py').read_bytes())]:
                item=tarfile.TarInfo(target)
                item.size,item.uid,item.gid,item.mode=len(data),10003,10003,0o644
                bundle.addfile(item,io.BytesIO(data))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=660)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        # CLI fixture trees contain intentional executable symlinks. Export only
        # ordinary evidence files; Windows need not recreate Linux symlinks.
        raw=subprocess.check_output(['docker','cp',name+':/workspace/.','-'],timeout=30)
        (output/'workspace.tar').write_bytes(raw);exported=True
        with tarfile.open(fileobj=io.BytesIO(raw)) as bundle:
            members={item.name.removeprefix('./'):item for item in bundle.getmembers() if item.isfile()}
            checks=json.loads(bundle.extractfile(members['checks.json']).read())
            runtime=json.loads(bundle.extractfile(members['runtime.json']).read())
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected for path,expected in inputs.items())
        verify_capture(runtime.get('integrated'),inputs,normalized)
        report=dict(runtime_image=image,inputs=inputs,lf_normalized_inputs=normalized,checks=checks,runtime_sources=runtime,controller_exit_code=run.returncode,
                    full_v05_accepted=False,v06_dependency_satisfied=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        passed=run.returncode==0 and set(checks)==set(CASES) and all(row['passed'] for row in checks.values())
        print(json.dumps(dict(output=str(output),passed=passed,checks=len(checks),failed={k:v.get('error') for k,v in checks.items() if not v['passed']})),flush=True)
        return int(not passed)
    finally:
        if exported:subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)
        else:print('Retained unexported container: '+name,flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
