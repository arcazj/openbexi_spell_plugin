"""Serialize unchanged native prompt/lifecycle controls on an explicit diagnostic overlay."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import traceback
import uuid

from installed_provenance import input_paths, verify_capture
from prompt_startup_provenance import RECIPES, qualification_identity

ROOT = Path(__file__).resolve().parents[1]
sha = lambda raw: hashlib.sha256(raw).hexdigest()
SUITES = ('early', 'lifecycle', 'removed', 'reopen', 'modes', 'abort', 'timeout', 'duplicate')


def sources_for(suite, composed=False):
    lifecycle = suite in ('early', 'lifecycle', 'removed', 'reopen')
    controller = ('child_lifecycle_reopen.py' if suite == 'reopen' else 'child_lifecycle_controller.py') if lifecycle else (
        'child_modes_controller.py' if suite in ('modes', 'abort') else 'prompt_timeout_controller.py')
    names = [controller, 'installed_provenance.py', 'prompt_startup_provenance.py']
    if lifecycle:
        names.append('child_lifecycle_provenance.py')
    else:
        names.append('child_modes_cases.py' if suite in ('modes', 'abort') else 'prompt_timeout_cases.py')
    sources = {name: (ROOT / 'conformance' / name).read_bytes() for name in names}
    text = sources[controller].decode()
    anchor = 'from installed_provenance import capture'
    assert text.count(anchor) == 1
    if not composed:
        text = text.replace(anchor, 'from prompt_startup_provenance import capture')
    if suite == 'early':
        text = text.replace("for operation in ('close', 'kill'):", "for trial in range(40):\n    operation = 'close'")
        text = text.replace("for phase in (('prompt', 'finished') if rejection or removed else ('prompt', 'finished', 'none')):", "for phase in ('none',):")
        text = text.replace("name = operation + '-' + phase", "name = operation + '-' + phase + '-' + str(trial)")
    sources[controller] = text.encode()
    if suite == 'abort':
        sources['child_modes_cases.py'] += b"\nCASES = {f'blocking-abort-{i}': CASES['blocking-abort'] for i in range(12)}\n"
    if suite == 'duplicate':
        sources['prompt_timeout_cases.py'] += b"\nCASES = {f'duplicate-{i}:boundary': CASES['duplicate:boundary'] for i in range(24)}\n"
    options = ['--externally-removed'] if suite == 'removed' else []
    return controller, sources, options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--suite', choices=SUITES, required=True)
    parser.add_argument('--composed', action='store_true', help='Require original installed-wheel provenance')
    args = parser.parse_args()
    assert args.image.startswith('sha256:') and len(args.image) == 71
    controller, sources, options = sources_for(args.suite, args.composed)
    names = list(dict.fromkeys([*input_paths(ROOT), *RECIPES.values(),
        'conformance/run_prompt_startup.py', 'conformance/prompt_startup_install.py',
        'conformance/prompt_startup.Dockerfile', 'conformance/prompt_startup.Dockerfile.dockerignore',
        *('conformance/' + name for name in sources),
        *(p.relative_to(ROOT).as_posix() for p in (ROOT / 'host_runtime/python').glob('*.py'))]))
    inputs = {name: sha((ROOT / name).read_bytes()) for name in names}
    output = ROOT / '.qualification/prompt-startup' / uuid.uuid4().hex
    output.mkdir(parents=True)
    name = 'openbexi-prompt-startup-' + output.name
    report = dict(passed=False, suite=args.suite, runtime_image=args.image, inputs=inputs,
        composed=args.composed,
        generated_sources={name:sha(raw) for name, raw in sources.items()},
        full_v05_accepted=False, full_v06_accepted=False)
    print('Evidence: ' + str(output), flush=True)
    created = False
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',args.image,'-u','/workspace/'+controller,*options],
            check=True,capture_output=True,timeout=30)
        created = True
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for filename, raw in sources.items():
                member = tarfile.TarInfo(filename)
                member.size, member.mode, member.uid, member.gid = len(raw),0o644,10003,10003
                archive.addfile(member,io.BytesIO(raw))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=stream.getvalue(),
            capture_output=True,check=True,timeout=30)
        with (output / 'controller.log').open('wb') as log:
            run = subprocess.run(['docker','start','-a',name],stdout=log,stderr=subprocess.STDOUT,
                timeout=900 if args.suite == 'early' else 360)
        report['controller_exit_code'] = run.returncode
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if created:
            try:
                raw = subprocess.check_output(['docker','cp',name+':/workspace/.','-'],timeout=30)
                (output / 'workspace.tar').write_bytes(raw)
                report['workspace_sha256'] = sha(raw)
                with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                    members = {m.name.removeprefix('./'):m for m in archive if m.isfile()}
                    read = lambda filename: archive.extractfile(members[filename]).read()
                    assert all(read(filename) == content for filename, content in sources.items())
                    if args.suite in ('early','lifecycle','removed','reopen'):
                        observed = json.loads(read('result.json'))
                        checks, runtime = observed['cases'], observed['runtime_sources']
                        report['observed'] = observed
                    else:
                        checks, runtime = json.loads(read('checks.json')), json.loads(read('runtime.json'))
                    report['checks'], report['runtime_sources'] = checks, runtime
                    if args.composed:
                        assert runtime is not None and 'prompt_startup_overlay' not in runtime
                        verify_capture(runtime, inputs)
                    else:
                        qualification_identity(runtime, inputs)
                    assert all(sha((ROOT / filename).read_bytes()) == digest for filename,digest in inputs.items())
                    expected = dict(early=40,lifecycle=6,removed=4,reopen=4,modes=9,abort=12,duplicate=24)
                    if args.suite == 'timeout':
                        from prompt_timeout_cases import CASES
                        expected['timeout'] = len(CASES)
                    report['passed'] = report.get('controller_exit_code') == 0 and len(checks) == expected[args.suite]
                    report['passed'] = report['passed'] and all(row['passed'] for row in checks.values())
            except Exception:
                report['capture_error'] = traceback.format_exc()
            finally:
                subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=30,check=True)
        report['passed'] = report['passed'] and not any(key.endswith('error') for key in report)
        (output / 'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(output), passed=report['passed'], checks=len(report.get('checks',{})),
        error=report.get('error',report.get('capture_error')))),flush=True)
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
