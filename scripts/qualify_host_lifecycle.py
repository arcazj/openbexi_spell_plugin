"""Installed headless CLI and host-loss checks against the actual native image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import uuid

def containers():
    return set(subprocess.check_output(['docker', 'ps', '-aq', '--filter',
        'label=org.openbexi.spell.host=1'], text=True, timeout=10).split())


def exact_image(identifier):
    if re.fullmatch(r'sha256:[0-9a-f]{64}', identifier) is None:
        raise ValueError('Qualification requires an exact local image SHA256, not a tag')
    actual = subprocess.check_output(['docker', 'image', 'inspect', identifier,
        '--format', '{{.Id}}'], text=True, timeout=10).strip()
    if actual != identifier:
        raise ValueError('Selected runtime image differs')
    return actual


def installed_host(interpreter, wheel, digest):
    helper = Path(__file__).with_name('qualify_host_input.py')
    probe = "import json,runpy,sys; f=runpy.run_path(sys.argv[1]); print(json.dumps(f['verify_installed_wheel'](sys.argv[2],sys.argv[3])))"
    return json.loads(subprocess.check_output([str(interpreter), '-I', '-c', probe,
        str(helper), str(wheel), digest], text=True, timeout=20))


def active_owned_image(baseline, image):
    active = containers()-baseline
    if len(active) != 1:
        raise ValueError('Expected exactly one live owned host container: '+repr(active))
    identifier, = active
    actual = subprocess.check_output(['docker', 'inspect', identifier, '--format', '{{.Image}}'],
                                    text=True, timeout=10).strip()
    if actual != image:
        raise ValueError('Live owned container used a different runtime image')
    return dict(container=identifier, image=actual)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interpreter', type=Path, required=True)
    parser.add_argument('--image', required=True, help='Exact candidate sha256 image ID')
    parser.add_argument('--wheel', type=Path, required=True, help='Exact host wheel already installed in --interpreter')
    parser.add_argument('--wheel-sha256', required=True)
    args = parser.parse_args()
    from openbexi_runtime.processes import ProcessTree
    evidence = Path(__file__).resolve().parents[1] / '.qualification/v0.6/lifecycle' / uuid.uuid4().hex
    project = evidence / 'project'
    project.mkdir(parents=True)
    report = {'passed': False, 'checks': [], 'runtime_instances': [],
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'installed_auditor_sha256': hashlib.sha256(Path(__file__).with_name('qualify_host_input.py').read_bytes()).hexdigest()}
    baseline = containers()
    def drained():
        deadline = time.monotonic() + 20
        while (remaining := containers() - baseline) and time.monotonic() < deadline:
            time.sleep(.1)
        assert not remaining, 'Owned host containers remain: ' + str(remaining)
    try:
        image = report['image'] = exact_image(args.image)
        interpreter, wheel = args.interpreter.resolve(), args.wheel.resolve()
        report['installed_host'] = installed_host(interpreter, wheel, args.wheel_sha256)
        environment = dict(os.environ, OPENBEXI_SPELL_IMAGE=image)
        environment.pop('OPENBEXI_HOST_MANAGED', None)
        (project / 'run.py').write_text("from spell.lang.functions import Display\nfrom pathlib import Path\nDisplay('INSTALLED_CLI_NATIVE')\nPath('answer.txt').write_text('42')\n")
        command = [str(args.interpreter.resolve()), '-I', '-m', 'openbexi_runtime.cli', 'run', 'run.py',
                   '--project', str(project), '--language', 'spell']
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45, env=environment)
        (evidence / 'cli.txt').write_text(completed.stdout + completed.stderr)
        assert completed.returncode == 0 and 'INSTALLED_CLI_NATIVE' in completed.stdout, completed.stderr
        assert [p.read_text() for p in project.glob('.openbexi/runs/*/artifacts/answer.txt')] == ['42']
        manifests = list(project.glob('.openbexi/runs/*/manifest.json'))
        assert len(manifests) == 1, manifests
        manifest = json.loads(manifests[0].read_bytes())
        assert manifest['image'] == image, manifest
        report['runtime_instances'].append(dict(mode='cli', image=manifest['image'],
            manifest_sha256=hashlib.sha256(manifests[0].read_bytes()).hexdigest()))
        drained()
        report['checks'].append('Installed neutral CLI discovers native SPELL backend, runs and exports')
        (project / 'loop.py').write_text("import time\nfrom spell.lang.functions import Display\nDisplay('HOST_LOSS_READY')\nwhile True:\n    time.sleep(0.02)\n")
        for mode in ('eof', 'process-tree-loss'):
            env = dict(environment, OPENBEXI_HOST_MANAGED='1')
            with (evidence / (mode + '.stderr')).open('wb') as errors:
                process = subprocess.Popen([str(args.interpreter.resolve()), '-I', '-u', '-m',
                    'openbexi_spell_host.runner', '--project', str(project), '--program', str(project / 'loop.py'), '--image', image],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, env=env,
                    start_new_session=os.name != 'nt')
                owner = ProcessTree(process.pid)
                output = queue.Queue()
                def read():
                    for line in process.stdout:
                        output.put(line)
                reader = threading.Thread(target=read)
                reader.start()
                try:
                    deadline = time.monotonic() + 40
                    while b'HOST_LOSS_READY' not in output.get(timeout=max(.01, deadline - time.monotonic())):
                        pass
                    report['runtime_instances'].append(dict(mode=mode, **active_owned_image(baseline, image)))
                    if mode == 'eof':
                        process.stdin.close()
                        assert process.wait(timeout=20) == 130
                    else:
                        owner.close()
                        process.wait(timeout=10)
                    drained()
                    report['checks'].append(mode + ': native container removed without an orphan')
                finally:
                    owner.close()
                    process.wait(timeout=10)
                    process.stdin.close()
                    reader.join(timeout=5)
                    process.stdout.close()
        assert report['installed_host'] == installed_host(interpreter, wheel, args.wheel_sha256)
        report['passed'] = True
    finally:
        (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(evidence, flush=True)


if __name__ == '__main__':
    main()
