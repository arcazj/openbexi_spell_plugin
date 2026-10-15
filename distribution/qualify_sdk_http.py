"""Build two offline SDK wheels and test HTTP rejection from a private install."""
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


PROBE = r'''
import base64, csv, hashlib, importlib.metadata, io, json
from pathlib import Path
import sys, zipfile
import dss.server, openbexi_spell_plugin
wheel = Path(sys.argv[1])
distribution = importlib.metadata.distribution('openbexi-spell-plugin')
prefix = Path(sys.prefix).resolve()
with zipfile.ZipFile(wheel) as archive:
    members = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    record, = [name for name in members if name.endswith('.dist-info/RECORD')]
    rows = list(csv.reader(io.StringIO(members[record].decode())))
    assert {row[0] for row in rows} == set(members)
    for name, digest, size in rows:
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        if name == record:
            continue  # pip adds its own installed metadata to RECORD.
        raw = members[name]
        assert digest == 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        assert len(raw) == int(size)
        installed = Path(distribution.locate_file(name)).resolve()
        assert installed.is_relative_to(prefix) and installed.read_bytes() == raw
    for package in ('dss', 'openbexi_spell_plugin', 'spell'):
        directory = Path(distribution.locate_file(package)).resolve()
        shipped = {name for name in members if name.startswith(package + '/')}
        actual = {package + '/' + file.relative_to(directory).as_posix()
                  for file in directory.rglob('*') if file.is_file() and '__pycache__' not in file.parts}
        assert shipped == actual, package
assert Path(dss.server.__file__).resolve() == Path(distribution.locate_file('dss/server.py')).resolve()
assert hashlib.sha256(Path(dss.server.__file__).read_bytes()).hexdigest() == sys.argv[2]
print(json.dumps({'passed': True, 'prefix': str(prefix), 'server_origin': dss.server.__file__,
                  'wheel_members_verified': len(rows) - 1, 'version': distribution.version}))
'''


def main():
    assert version('setuptools') == '80.9.0'
    output = ROOT / '.qualification/sdk-http' / uuid.uuid4().hex
    output.mkdir(parents=True)
    names = subprocess.check_output(['git', 'ls-files', '-z', '--', 'src', 'pyproject.toml',
                                     'README.md', 'LICENSE', 'NOTICE'], cwd=ROOT).decode().split('\0')
    inputs = {name: sha(ROOT / name) for name in names if name}
    tests = ROOT / 'tests/test_dss_transports.py'
    lock = ROOT / 'distribution/pipe-test-requirements.lock'
    cache = json.loads((ROOT / 'distribution/evidence/pipe-test-wheelhouse.json').read_bytes())
    report = {'passed': False, 'scope': 'Windows CPython 3.13 SDK wheel and HTTP rejection; no native host or release acceptance',
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'inputs': inputs, 'builder_sha256': sha(Path(__file__)), 'tests_sha256': sha(tests),
              'test_lock_sha256': sha(lock), 'python': sys.version, 'setuptools': version('setuptools'),
              'source_date_epoch': '1767225600', 'builds': [], 'commands': []}

    def run(name, command, **kwargs):
        result = subprocess.run(command, capture_output=True, timeout=180, **kwargs)
        log = output / (name + '.log')
        log.write_bytes(result.stdout + result.stderr)
        report['commands'].append({'command': list(map(str, command)), 'exit_code': result.returncode,
                                   'log': {'path': str(log), 'sha256': sha(log)}})
        result.check_returncode()
        return result.stdout

    try:
        for name in ('a', 'b'):
            build = output / name
            source = build / 'source'
            for relative in inputs:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            run(name, [sys.executable, '-m', 'pip', 'wheel', '--no-cache-dir', '--no-index',
                       '--no-deps', '--no-build-isolation', '--wheel-dir', str(build / 'wheels'), str(source)],
                env=dict(os.environ, SOURCE_DATE_EPOCH=report['source_date_epoch']))
            wheel, = (build / 'wheels').glob('*.whl')
            report['builds'].append({'path': str(wheel), 'sha256': sha(wheel)})
        assert report['builds'][0]['sha256'] == report['builds'][1]['sha256']
        environment = output / 'private'
        run('venv', [sys.executable, '-m', 'venv', str(environment)])
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        wheelhouse = output / 'test-wheels'
        wheelhouse.mkdir()
        for entry in cache['wheels'].values():
            retained = Path(entry['path'])
            assert sha(retained) == entry['sha256']
            (wheelhouse / retained.name).write_bytes(retained.read_bytes())
        run('test-dependencies', [str(python), '-I', '-m', 'pip', 'install', '--no-index', '--find-links',
                                 str(wheelhouse), '--require-hashes', '-r', str(lock)])
        run('install', [str(python), '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)])
        probe = output / 'verify_install.py'
        probe.write_text(PROBE, encoding='utf-8', newline='\n')
        report['installed'] = json.loads(run('installed', [str(python), '-I', str(probe), str(wheel),
                                                         inputs['src/dss/server.py']]))
        isolated_tests = output / 'tests'
        isolated_tests.mkdir()
        (isolated_tests / tests.name).write_bytes(tests.read_bytes())
        junit = output / 'transports.xml'
        run('transports', [str(python), '-I', '-m', 'pytest', str(isolated_tests), '-q',
                           '--junitxml=' + str(junit)], cwd=output)
        suites = ET.parse(junit).getroot().iter('testsuite')
        totals = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
        for suite in suites:
            for key in totals:
                totals[key] += int(suite.get(key, '0'))
        assert totals == {'tests': 22, 'failures': 0, 'errors': 0, 'skipped': 0}, totals
        report['tests'] = {**totals, 'path': str(junit), 'sha256': sha(junit)}
        run('remove', [str(python), '-I', '-m', 'pip', 'uninstall', '-y', 'openbexi-spell-plugin'])
        run('removed', [str(python), '-I', '-c',
                        "import importlib.util; assert all(importlib.util.find_spec(n) is None for n in ('dss','spell','openbexi_spell_plugin'))"])
        assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
        assert sha(tests) == report['tests_sha256'] and sha(lock) == report['test_lock_sha256']
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'output': str(output), 'passed': report['passed'], 'error': report.get('error')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
