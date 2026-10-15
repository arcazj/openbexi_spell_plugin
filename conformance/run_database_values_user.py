"""Retain native user-database persistence and source identities."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from user_database_cases import CASES, EXAMPLE
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    output=ROOT / '.qualification/database-values-user' / uuid.uuid4().hex
    output.mkdir(parents=True)
    names=['conformance/user_database_cases.py','conformance/database_values_user_controller.py','conformance/run_database_values_user.py','conformance/user_database_prompts.py',
           'source_port/user_database_patches.py','conformance/user_database.Dockerfile','conformance/user_database.Dockerfile.dockerignore',
           'source_port/native_patches.py','source_port/patches.py','source_port/data_files_patches.py','source_port/data_files_native_patches.py',
           'source_port/database_import_patches.py','host_runtime/python/native.py',
           'conformance/inventory.json','docs/reference/SPELL2.6.10-src.zip','docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    names += input_paths(ROOT)
    names += ['conformance/database_values_provenance.py', 'conformance/database_values.Dockerfile', 'conformance/user_database_controller.py']
    inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    normalized={name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in names}
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-database-values-user-'+uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--init','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
                        '--entrypoint','python',image,'-I','/workspace/controller.py'],check=True,capture_output=True)
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            for target,data in [('controller.py',(ROOT/'conformance/database_values_user_controller.py').read_bytes()),('user_database_prompts.py',(ROOT/'conformance/user_database_prompts.py').read_bytes()),('cases.json',json.dumps(CASES).encode()),('example.json',json.dumps(EXAMPLE).encode()),('installed_provenance.py',(ROOT/'conformance/installed_provenance.py').read_bytes()),('database_values_provenance.py',(ROOT/'conformance/database_values_provenance.py').read_bytes())]:
                item=tarfile.TarInfo(target)
                item.size,item.uid,item.gid,item.mode=len(data),10003,10003,0o644
                bundle.addfile(item,io.BytesIO(data))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=660)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        # CLI fixture trees contain intentional executable symlinks. Export only
        # ordinary evidence files; Windows need not recreate Linux symlinks.
        raw=subprocess.check_output(['docker','cp',name+':/workspace/.','-'],timeout=30)
        (output/'workspace.tar').write_bytes(raw)
        with tarfile.open(fileobj=io.BytesIO(raw)) as bundle:
            members={item.name.removeprefix('./'):item for item in bundle.getmembers() if item.isfile()}
            checks=json.loads(bundle.extractfile(members['checks.json']).read())
            runtime=json.loads(bundle.extractfile(members['runtime.json']).read())
            prompts=json.loads(bundle.extractfile(members['prompts.json']).read())
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected for path,expected in inputs.items())
        verify_capture(runtime.get('integrated'),inputs,normalized)
        assert runtime['host_inputs']['/opt/host/native.py']==inputs['host_runtime/python/native.py']
        if runtime.get('overlay'):
            for name,key in [('database_values_patches.py','source_port/database_values_patches.py'),('database_values_provenance.py','conformance/database_values_provenance.py'),('database_values.Dockerfile','conformance/database_values.Dockerfile')]:
                assert runtime['overlay']['files'][name]==inputs[key],name
        report=dict(runtime_image=image,inputs=inputs,lf_normalized_inputs=normalized,checks=checks,prompts=prompts,runtime_sources=runtime,controller_exit_code=run.returncode,
                    full_v05_accepted=False,v06_dependency_satisfied=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(output=str(output),checks=len(checks),failed={k:v.get('error') for k,v in checks.items() if not v['passed']},prompts={k:{a:b for a,b in v.items() if a not in ('events','prompts')} for k,v in prompts.items()}),indent=2))
        return int(run.returncode != 0 or set(checks)!=set(CASES) or any(not row['passed'] for row in checks.values()) or any(not row['passed'] for row in prompts.values()))
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
