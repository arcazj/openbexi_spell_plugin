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


def inside(context=False):
    patch=Path('/child-lifecycle-patch')
    manifest=json.loads((patch/'manifest.json').read_bytes())
    assert manifest['mode']=='child-lifecycle'
    for name,expected in manifest['original_artifacts'].items():
        assert sha(Path('/out')/name)==expected,name
        assert sha(patch/'compiled'/name)==manifest['artifacts'][name]
        shutil.copyfile(patch/'compiled'/name,Path('/out')/name)
    output=Path('/child-lifecycle-gate')
    output.mkdir()
    # The cached native stage has prior gate markers. Preserve then remove only
    # regular text markers in this disposable /out directory before fresh tests.
    prior=output/'prior-fixture-markers'
    prior.mkdir()
    prior_markers={}
    for path in Path('/out').glob('*.txt'):
        assert path.parent==Path('/out') and path.is_file() and not path.is_symlink(),path
        prior_markers[path.name]=sha(path)
        shutil.copyfile(path,prior/path.name)
        path.unlink()
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',PYTHONMALLOC='malloc',
        SPELL_HOME='/source',SPELL_DATA='/out/executor-data',SPELL_CONFIG='/out/executor-config')
    qualifier='/context/qualify_context.py' if context else '/executor/qualify_executor.py'
    if context:
        # The immutable cached build already contains these precise fixture
        # symlinks. Remove only those links inside this disposable container so
        # the unmodified original context gate can recreate its own fixtures.
        for name,target in [('SPELL-Context','SPELL-Context'),('SPELL-Executor','SPELL-Executor_v3'),
                ('SPELL-Executor_v3','SPELL-Executor_v3'),('SPELL-Service','SPELL-Service_v3')]:
            link=Path('/source/bin')/name
            assert link.is_symlink() and link.readlink()==Path('/out')/target,(link,link.readlink())
            link.unlink()
    result=subprocess.run([sys.executable,'-I',qualifier],env=env,
        capture_output=True,timeout=420 if context else 180)
    (output/('context-qualification.log' if context else 'executor-qualification.log')).write_bytes(result.stdout+result.stderr)
    gate_name='context' if context else 'executor'
    reports=[Path('/out')/(gate_name+'-runtime.json'),*Path('/out').glob('*.log'),
        *Path('/out').glob('*-capture.log'),*Path('/out').glob('*-resume.log')]
    for path in reports:
        shutil.copyfile(path,output/path.name)
    report=dict(exit_code=result.returncode,gate=json.loads((Path('/out')/(gate_name+'-runtime.json')).read_bytes()),
        qualifier_sha256=sha(Path(qualifier)), gate_name=gate_name,
        runtime_sha256=sha(Path('/out/libspell_executor313.so')),
        standalone_sha256=sha(Path('/out/SPELL-ExecutorCmd_v3')),overlay=manifest,
        native_artifacts={name:sha(Path('/out')/name) for name in manifest['artifacts']},
        prior_fixture_markers=prior_markers,
        outputs={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return result.returncode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside',action='store_true')
    parser.add_argument('--native-image')
    parser.add_argument('--context',action='store_true')
    args=parser.parse_args()
    if args.inside:return inside(args.context)
    root=Path(__file__).resolve().parents[1]
    output=root/'.qualification/v0.6/child-lifecycle-gate'/uuid.uuid4().hex
    output.mkdir(parents=True)
    image=subprocess.check_output(['docker','image','inspect',args.native_image,'--format','{{.Id}}'],text=True).strip()
    name='openbexi-child-lifecycle-gate-'+uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',name,'--network','none','--init',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-I','/child-lifecycle-gate-controller.py','--inside',*(['--context'] if args.context else [])],
            check=True,capture_output=True)
        subprocess.run(['docker','cp',str(Path(__file__)),name+':/child-lifecycle-gate-controller.py'],
            check=True,capture_output=True)
        run=subprocess.run(['docker','start','-a',name],capture_output=True,timeout=480 if args.context else 240)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        subprocess.run(['docker','cp',name+':/child-lifecycle-gate/.',str(output)],check=True,capture_output=True)
        report=json.loads((output/'result.json').read_bytes())
        report.update(native_image=image,controller_sha256=sha(Path(__file__)),
            controller_exit_code=run.returncode,full_v06_accepted=False)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(output=str(output),gate=report['gate'],exit_code=run.returncode),indent=2))
        return run.returncode
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__=='__main__':raise SystemExit(main())
