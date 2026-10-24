"""Run an existing installed v0.7 native/DSS test and retain its process evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed-tests', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    selected = args.installed_tests / 'tests/native_driver_acceptance.py'
    image = 'sha256:d99b095d65c7fef008f9e6c02ff95c678cff295ee85a129f7a62fc0b795b1283'
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OPENBEXI_NATIVE_TEST_IMAGE=image)
    env.pop('PYTEST_ADDOPTS', None)
    command = [sys.executable, '-I', '-m', 'pytest', str(selected) + '::test_original_native_driver_manager_rpc_binary_command',
               '-q', '-c', str(args.installed_tests / 'pytest.ini'),
               '--junitxml=' + str((args.output / 'native.xml').resolve())]
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'command': command,
              'image': image, 'selected_test_sha256': hashlib.sha256(selected.read_bytes()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'installed_versions': {p: importlib.metadata.version(p) for p in
                  ('openbexi-ide', 'openbexi-spell-host', 'openbexi-spell-shared', 'openbexi-spell-dss')},
              'snapshots': [], 'passed': False}
    with (args.output / 'native.log').open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        report['test_process_pid'] = process.pid
        while process.poll() is None:
            if time.monotonic() - (started := report.setdefault('_started', time.monotonic())) > 180:
                process.kill()
                break
            containers = subprocess.check_output(['docker', 'ps', '-q', '--filter',
                'name=openbexi-native-shared-'], text=True, timeout=10).split()
            for container in containers:
                snapshot = {'elapsed_seconds': round(time.monotonic() - started, 3), 'container': container}
                top = subprocess.run(['docker', 'top', container, '-eo', 'pid,ppid,comm'],
                                     capture_output=True, text=True, timeout=10)
                snapshot['top'] = top.stdout.splitlines()
                # Only public /proc socket tables, not environment or credentials.
                probe = subprocess.run(['docker', 'exec', container, 'python', '-I', '-c',
                    "from pathlib import Path; import json; print(json.dumps({p:Path(p).read_text() for p in ['/proc/net/tcp','/proc/net/tcp6']}))"],
                    capture_output=True, text=True, timeout=10)
                if probe.returncode == 0:
                    snapshot['sockets'] = json.loads(probe.stdout)
                report['snapshots'].append(snapshot)
            time.sleep(.4)
        report['exit_code'] = process.wait(timeout=15)
    report.pop('_started', None)
    all_names = '\n'.join('\n'.join(s['top']) for s in report['snapshots'])
    report['native_processes_seen'] = {name: name in all_names for name in
                                      ('SPELL-Listener', 'SPELL-Context', 'SPELL-Executor')}
    report['passed'] = report['exit_code'] == 0 and all(report['native_processes_seen'].values())
    (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('passed', 'exit_code', 'native_processes_seen')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
