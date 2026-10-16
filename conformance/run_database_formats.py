"""Retain native user-database persistence and source identities."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

from database_format_cases import CASES as FORMAT_CASES
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--suite',choices=('formats','user','values'),default='formats')
    args=parser.parse_args()
    output=ROOT / '.qualification/database-formats' / args.suite / uuid.uuid4().hex
    example=None
    if args.suite=='user':
        from user_database_cases import CASES,EXAMPLE as example
        controller='user_database_controller.py'
    elif args.suite=='values':
        from database_values_cases import CASES
        controller='database_values_controller.py'
    else:CASES=FORMAT_CASES;controller='database_format_controller.py'
    source=(ROOT/'conformance'/controller).read_text(encoding='utf-8')
    if args.suite=='values':source=source.replace('from database_values_provenance import capture','from database_format_provenance import capture')
    else:
        source=source.replace('from installed_provenance import capture','from database_format_provenance import capture')
        start=source.index('report=dict(installed=installed,manifest=')
        end=source.index('\n',start)
        source=source[:start]+'report=capture()'+source[end:]
    generated=source.encode('utf-8')
    output.mkdir(parents=True)
    names=['conformance/database_format_cases.py','conformance/database_format_controller.py','conformance/run_database_formats.py','host_runtime/python/native.py','conformance/inventory.json','docs/reference/SPELL2.6.10-src.zip','docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    names += ['conformance/'+controller,'source_port/database_format_patches.py','conformance/database_format_provenance.py','conformance/database_format.Dockerfile','conformance/database_format.Dockerfile.dockerignore','conformance/user_database_cases.py','conformance/user_database_prompts.py','conformance/database_values_cases.py','conformance/database_import_cases.py']
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
            for target,data in [('controller.py',generated),('cases.json',json.dumps(CASES).encode()),('example.json',json.dumps(example).encode()),('user_database_prompts.py',(ROOT/'conformance/user_database_prompts.py').read_bytes()),('database_format_provenance.py',(ROOT/'conformance/database_format_provenance.py').read_bytes()),('installed_provenance.py',(ROOT/'conformance/installed_provenance.py').read_bytes())]:
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
            prompts=json.loads(bundle.extractfile(members['prompts.json']).read()) if args.suite=='user' else {}
            assert bundle.extractfile(members['controller.py']).read()==generated
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected for path,expected in inputs.items())
        verify_capture(runtime.get('integrated'),inputs,normalized)
        report=dict(suite=args.suite,generated_controller_sha256=hashlib.sha256(generated).hexdigest(),prompts=prompts,runtime_image=image,inputs=inputs,lf_normalized_inputs=normalized,checks=checks,runtime_sources=runtime,controller_exit_code=run.returncode,
                    full_v05_accepted=False,v06_dependency_satisfied=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        passed=run.returncode==0 and set(checks)==set(CASES) and all(row['passed'] for row in checks.values()) and all(row['passed'] for row in prompts.values())
        print(json.dumps(dict(output=str(output),passed=passed,checks=len(checks),failed={k:v.get('error') for k,v in checks.items() if not v['passed']})),flush=True)
        return int(not passed)
    finally:
        if exported:subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)
        else:print('Retained unexported container: '+name,flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
