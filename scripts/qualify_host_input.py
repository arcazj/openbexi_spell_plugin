"""Run retained FIFO/EOF oracles against an exact installed host wheel.

The controlled DAP peer proves client pipe transport, not native execution.
Run with the private CPython 3.13 interpreter containing the selected wheel and
pytest 8.4.2. No package installation, Docker operation or network is performed.
"""
import argparse
import base64
import csv
import hashlib
from importlib import metadata
import io
import json
from pathlib import Path, PurePosixPath
import platform
import sys
import traceback
import xml.etree.ElementTree as ET
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wheel_payload(wheel, expected_sha):
    if sha(wheel) != expected_sha:
        raise ValueError('Selected host wheel SHA256 differs')
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
                PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts
                or '\\' in name or name.endswith('/') for name in names):
            raise ValueError('Wheel has ambiguous or unsafe members')
        records = [name for name in names if name.endswith('.dist-info/RECORD')]
        if len(records) != 1:
            raise ValueError('Wheel must have one RECORD')
        record, = records
        rows = list(csv.reader(io.StringIO(archive.read(record).decode('utf-8'))))
        if any(len(row) != 3 for row in rows) or len({r[0] for r in rows}) != len(rows):
            raise ValueError('Wheel RECORD rows are invalid or duplicated')
        if {r[0] for r in rows} != set(names):
            raise ValueError('Wheel RECORD does not cover the complete member set')
        payload = {}
        for name, digest, size in rows:
            if name == record:
                if digest or size:
                    raise ValueError('Wheel RECORD must omit its own hash and size')
                continue
            raw = archive.read(name)
            expected = 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
            if digest != expected or size != str(len(raw)):
                raise ValueError('Wheel RECORD mismatch: '+name)
            if not (name.startswith('openbexi_spell_host/') or name.startswith(record.rsplit('/', 1)[0]+'/')):
                raise ValueError('Unexpected host wheel payload: '+name)
            payload[name] = raw
        if 'openbexi_spell_host/__init__.py' not in payload:
            raise ValueError('Host package is missing')
        return payload


def verify_installed_wheel(wheel, expected_sha):
    if sys.version_info[:2] != (3, 13):
        raise ValueError('The supported qualification profile is CPython 3.13')
    if platform.python_implementation() != 'CPython':
        raise ValueError('The qualification profile requires CPython')
    payload = wheel_payload(wheel, expected_sha)
    package = metadata.distribution('openbexi-spell-host')
    import openbexi_spell_host
    origin = Path(openbexi_spell_host.__file__).resolve()
    prefix = Path(sys.prefix).resolve()
    if not origin.is_relative_to(prefix) or origin != Path(package.locate_file('openbexi_spell_host/__init__.py')).resolve():
        raise ValueError('Host import does not originate in the selected installed environment')
    files = {}
    for name, raw in payload.items():
        path = Path(package.locate_file(name)).resolve()
        if not path.is_relative_to(prefix) or path.read_bytes() != raw:
            raise ValueError('Installed wheel payload mismatch: '+name)
        files[name] = hashlib.sha256(raw).hexdigest()
    expected_sources = {name for name in payload if name.startswith('openbexi_spell_host/') and name.endswith('.py')}
    actual_sources = {'openbexi_spell_host/'+path.relative_to(origin.parent).as_posix()
                      for path in origin.parent.rglob('*.py')}
    if actual_sources != expected_sources:
        raise ValueError('Installed host Python source set differs from the wheel')
    if openbexi_spell_host.__version__ != package.version:
        raise ValueError('Host package and module versions differ')
    return dict(python=sys.version, implementation=platform.python_implementation(),
        platform=platform.system(), interpreter=sys.executable, prefix=str(prefix),
        package_origin=str(origin), version=package.version, wheel_sha256=expected_sha,
        wheel_members_verified=len(files), installed_members=files)


def bind_installed_tests(raw, site):
    text = raw.decode('utf-8')
    anchor = "HOST_SOURCE = Path(__file__).resolve().parents[1] / 'src'"
    if text.count(anchor) != 1:
        raise ValueError('Retained test import anchor changed')
    # Every child inherits this exact installed site; none can see checkout src.
    replacement = 'HOST_SOURCE = Path('+repr(str(Path(site).resolve()))+')'
    return text.replace(anchor, replacement).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--wheel-sha256', required=True)
    parser.add_argument('--tests', type=Path, required=True)
    parser.add_argument('--tests-sha256', required=True)
    parser.add_argument('--expected-platform', choices=('Linux', 'Windows'), required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory for retained test copies and evidence')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, scope='Installed host FIFO/EOF transport with controlled DAP peer; no native runtime or release acceptance',
        harness_sha256=sha(__file__), original_tests_sha256=args.tests_sha256,
        expected_platform=args.expected_platform, full_v06_accepted=False)
    try:
        if platform.system() != args.expected_platform:
            raise ValueError('Actual platform differs from requested qualification profile')
        report['installed'] = verify_installed_wheel(args.wheel, args.wheel_sha256)
        if sha(args.tests) != args.tests_sha256:
            raise ValueError('Retained pipe-test source SHA256 differs')
        raw = args.tests.read_bytes()
        (output/'original_test_runner_input.py').write_bytes(raw)
        site = Path(report['installed']['package_origin']).parent.parent
        bound = bind_installed_tests(raw, site)
        test = output/'test_runner_input.py'
        test.write_bytes(bound)
        report['adapted_tests_sha256'] = sha(test)
        if metadata.version('pytest') != '8.4.2':
            raise ValueError('Use the pinned pytest 8.4.2 test dependency')
        import os
        import subprocess
        environment = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        environment.pop('PYTHONPATH', None)
        config = output/'pytest.ini'
        config.write_text('[pytest]\n', encoding='utf-8')
        with (output/'pytest.log').open('wb') as log:
            result = subprocess.run([sys.executable, '-I', '-m', 'pytest', '-q', '-c', str(config),
                '-o', 'addopts=', str(test), '--basetemp='+str(output/'cases'),
                '--junitxml='+str(output/'tests.xml')], cwd=output, env=environment, stdout=log, stderr=subprocess.STDOUT)
        report['exit_code'] = result.returncode
        suites = ET.parse(output/'tests.xml').getroot()
        counts = {key:sum(int(row.get(key, 0)) for row in suites.iter('testsuite'))
                  for key in ('tests', 'failures', 'errors', 'skipped')}
        report['tests'] = counts
        if result.returncode or counts != dict(tests=16, failures=0, errors=0, skipped=0):
            raise ValueError('Installed pipe suite did not pass all 16 cases')
        if report['installed'] != verify_installed_wheel(args.wheel, args.wheel_sha256):
            raise ValueError('Installed host payload changed during the tests')
        if sha(args.tests) != args.tests_sha256 or test.read_bytes() != bound:
            raise ValueError('Pipe test source changed during qualification')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        report['evidence_files'] = {p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps(dict(passed=report['passed'], evidence=str(output)), indent=2), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
