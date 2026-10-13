"""Retain actual native data-container client-editing observations."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-dss:v05-dta-ipc-development')
    args = parser.parse_args()
    output = ROOT/'.qualification/v0.5/dta-edit'/uuid.uuid4().hex
    output.mkdir(parents=True)
    names = ['conformance/dta_edit_controller.py', 'conformance/run_dta_edit.py',
             'source_port/dta_native_patches.py', 'source_port/dta_time_patches.py',
             'source_port/dta_ipc_patches.py', 'conformance/dta_ipc_build.py',
             'conformance/dta_ipc.Dockerfile', 'conformance/dta_ipc.Dockerfile.dockerignore',
             'source_port/ui_native_patches.py', 'source_port/data_files_native_patches.py',
             'source_port/flow_patches.py', 'source_port/flow_analyze.py',
             'source_port/native_patches.py', 'distribution/incremental_native.py',
             'docs/reference/SPELL2.6.10-src.zip', 'docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    names = list(dict.fromkeys(names + input_paths(ROOT)))
    inputs = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    normalized = {name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                  for name in names if name.endswith('.py')}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name = 'openbexi-dta-edit-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','256','--entrypoint','python',image,
            '-I','/workspace/controller.py'],check=True,capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            content = (ROOT/'conformance/dta_edit_controller.py').read_bytes()
            (output/'controller.py').write_bytes(content)
            entry = tarfile.TarInfo('controller.py')
            entry.size,entry.mode,entry.uid,entry.gid = len(content),0o644,10003,10003
            bundle.addfile(entry,io.BytesIO(content))
            helper = (ROOT/'conformance/installed_provenance.py').read_bytes()
            entry = tarfile.TarInfo('installed_provenance.py')
            entry.size,entry.mode,entry.uid,entry.gid = len(helper),0o644,10003,10003
            bundle.addfile(entry,io.BytesIO(helper))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        result = subprocess.run(['docker','start','-a',name],capture_output=True,timeout=150)
        (output/'controller.log').write_bytes(result.stdout+result.stderr)
        subprocess.run(['docker','cp',name+':/workspace/.',str(output/'workspace')],check=True,capture_output=True)
        subprocess.run(['docker','cp',name+':/tmp',str(output/'native-tmp')],capture_output=True)
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in inputs.items())
        report = dict(runtime_image=image,inputs=inputs,lf_normalized_inputs=normalized,controller_exit=result.returncode)
        path = output/'workspace/dta-edit-results.json'
        if path.exists(): report.update(json.loads(path.read_bytes()))
        verify_capture(report.get('runtime_sources',{}).get('integrated'),inputs,normalized)
        for recipe, expected in report.get('runtime_sources', {}).get('manifest', {}).get('recipes', {}).items():
            source = next(name for name in names if name.endswith('/' + recipe))
            assert expected in (inputs[source], normalized.get(source)), 'Installed recipe is stale: ' + source
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(evidence=str(output),passed=report.get('passed',False),controller_exit=result.returncode),indent=2))
        return result.returncode or int(not report.get('passed', False))
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
