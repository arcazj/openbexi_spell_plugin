"""Run the existing full standalone executor gate against the explicit overlay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside():
    patch=Path('/checkpoint-error-patch')
    manifest=json.loads((patch/'manifest.json').read_bytes())
    assert manifest['mode']=='fix'
    for name,expected in manifest['original_artifacts'].items():
        assert sha(Path('/out')/name)==expected,name
        assert sha(patch/'compiled'/name)==manifest['artifacts'][name]
        shutil.copyfile(patch/'compiled'/name,Path('/out')/name)
    output=Path('/checkpoint-gate')
    output.mkdir()
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',PYTHONMALLOC='malloc',
        SPELL_HOME='/source',SPELL_DATA='/out/executor-data',SPELL_CONFIG='/out/executor-config')
    result=subprocess.run([sys.executable,'-I','/executor/qualify_executor.py'],env=env,
        capture_output=True,timeout=180)
    (output/'executor-qualification.log').write_bytes(result.stdout+result.stderr)
    reports=[Path('/out/executor-runtime.json'),*Path('/out').glob('executor-*.log'),
        *Path('/out').glob('*-capture.log'),*Path('/out').glob('*-resume.log')]
    for path in reports:
        shutil.copyfile(path,output/path.name)
    report=dict(exit_code=result.returncode,gate=json.loads(Path('/out/executor-runtime.json').read_bytes()),
        qualifier_sha256=sha(Path('/executor/qualify_executor.py')),
        runtime_sha256=sha(Path('/out/libspell_executor313.so')),
        standalone_sha256=sha(Path('/out/SPELL-ExecutorCmd_v3')),overlay=manifest,
        outputs={p.name:sha(p) for p in output.iterdir()})
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return result.returncode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside',action='store_true')
    parser.add_argument('--native-image')
    args=parser.parse_args()
    if args.inside:return inside()
    root=Path(__file__).resolve().parents[1]
    output=root/'.qualification/v0.6/checkpoint-error-gate'/uuid.uuid4().hex
    output.mkdir(parents=True)
    image=subprocess.check_output(['docker','image','inspect',args.native_image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-checkpoint-gate-'+uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--network','none','--init',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-I','/checkpoint-gate-controller.py','--inside'],
            check=True,capture_output=True)
        subprocess.run(['docker','cp',str(Path(__file__)),name+':/checkpoint-gate-controller.py'],
            check=True,capture_output=True)
        run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=240)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        subprocess.run(['docker','cp',name+':/checkpoint-gate/.',str(output)],check=True,capture_output=True)
        report=json.loads((output/'result.json').read_bytes())
        report.update(native_image=image,controller_sha256=sha(Path(__file__)),
            controller_exit_code=run.returncode,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(output=str(output),gate=report['gate'],exit_code=run.returncode),indent=2))
        return run.returncode
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__=='__main__':raise SystemExit(main())
