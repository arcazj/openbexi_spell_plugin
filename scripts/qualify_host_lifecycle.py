"""Installed headless CLI and host-loss checks against the actual native image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid

from openbexi_runtime.processes import ProcessTree


def containers():
    return set(subprocess.check_output(['docker', 'ps', '-aq', '--filter',
        'label=org.openbexi.spell.host=1'], text=True, timeout=10).split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interpreter', type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parents[1] / '.qualification/v0.3/lifecycle' / uuid.uuid4().hex
    project = evidence / 'project'
    project.mkdir(parents=True)
    report = {'passed': False, 'checks': [], 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    baseline = containers()
    def drained():
        deadline = time.monotonic() + 20
        while (remaining := containers() - baseline) and time.monotonic() < deadline:
            time.sleep(.1)
        assert not remaining, 'Owned host containers remain: ' + str(remaining)
    try:
        (project / 'run.py').write_text("from spell.lang.functions import Display\nfrom pathlib import Path\nDisplay('INSTALLED_CLI_NATIVE')\nPath('answer.txt').write_text('42')\n")
        command = [str(args.interpreter.resolve()), '-I', '-m', 'openbexi_runtime.cli', 'run', 'run.py',
                   '--project', str(project), '--language', 'spell']
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
        (evidence / 'cli.txt').write_text(completed.stdout + completed.stderr)
        assert completed.returncode == 0 and 'INSTALLED_CLI_NATIVE' in completed.stdout, completed.stderr
        assert [p.read_text() for p in project.glob('.openbexi/runs/*/artifacts/answer.txt')] == ['42']
        drained()
        report['checks'].append('Installed neutral CLI discovers native SPELL backend, runs and exports')
        (project / 'loop.py').write_text("import time\nfrom spell.lang.functions import Display\nDisplay('HOST_LOSS_READY')\nwhile True:\n    time.sleep(0.02)\n")
        for mode in ('eof', 'process-tree-loss'):
            env = dict(os.environ, OPENBEXI_HOST_MANAGED='1')
            with (evidence / (mode + '.stderr')).open('wb') as errors:
                process = subprocess.Popen([str(args.interpreter.resolve()), '-I', '-u', '-m',
                    'openbexi_spell_host.runner', '--project', str(project), '--program', str(project / 'loop.py')],
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
        report['passed'] = True
    finally:
        report['image'] = subprocess.check_output(['docker', 'image', 'inspect',
            'openbexi-spell-host:0.3.0', '--format', '{{.Id}}'], text=True).strip()
        (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(evidence, flush=True)


if __name__ == '__main__':
    main()
