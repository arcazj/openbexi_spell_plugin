"""Qualify installed host/shared Python package upgrade and removal offline.

This does not execute a native SPELL process or qualify an IDE integration.
"""
import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib.metadata as metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wheel_identity(path):
    with ZipFile(path) as archive:
        name, = (item for item in archive.namelist() if item.endswith('.dist-info/METADATA'))
        info = BytesParser().parsebytes(archive.read(name))
    return {'path': str(path), 'sha256': sha(path), 'name': info['Name'],
            'version': info['Version'], 'requires_dist': info.get_all('Requires-Dist', [])}


def installed_wheel(identity):
    """Verify every wheel payload against both RECORD and its installed copy."""
    distribution = metadata.distribution(identity['name'])
    assert distribution.version == identity['version'], 'Installed distribution version differs'
    assert distribution.requires == (identity['requires_dist'] or None), 'Installed requirements differ'
    path = Path(identity['path'])
    assert sha(path) == identity['sha256'], 'Input wheel changed'
    with ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate wheel members'
        record_name, = (name for name in names if name.endswith('.dist-info/RECORD'))
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
        assert len(rows) == len(names) and {row[0] for row in rows} == set(names), 'Incomplete wheel RECORD'
        payloads = {}
        for name, digest, size in rows:
            if name == record_name:
                assert not digest and not size
                continue
            data = archive.read(name)
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            assert digest == 'sha256=' + expected and int(size) == len(data), 'Wheel RECORD mismatch: ' + name
            installed = Path(distribution.locate_file(name)).resolve()
            assert installed.is_relative_to(Path(sys.prefix).resolve()), 'Package escaped fresh environment'
            assert installed.read_bytes() == data, 'Installed payload differs: ' + name
            payloads[name] = hashlib.sha256(data).hexdigest()
    installed_rows = list(csv.reader(io.StringIO(distribution.read_text('RECORD'))))
    assert len(installed_rows) == len({row[0] for row in installed_rows}), 'Duplicate installed RECORD rows'
    for name, digest, size in installed_rows:
        installed = Path(distribution.locate_file(name)).resolve()
        assert installed.is_relative_to(Path(sys.prefix).resolve()), 'RECORD escaped fresh environment'
        assert installed.is_file(), 'Installed RECORD path missing: ' + name
        if digest:
            data = installed.read_bytes()
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            assert digest == 'sha256=' + expected and int(size) == len(data), 'Installed RECORD mismatch: ' + name
        else:
            assert name.endswith(('.pyc', '/RECORD')) and not size, 'Unexpected unhashed installed file'
    return {'name': distribution.metadata['Name'], 'version': distribution.version,
            'requires_dist': distribution.requires or [], 'wheel_record_entries': len(rows),
            'installed_record_entries': len(installed_rows), 'record_verified': True,
            'installed_payload_sha256': payloads}


def probe(config_path, result_path):
    """Runs under the fresh interpreter with -I; imports installed packages only."""
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    report = {'passed': False, 'phase': config['phase'], 'python': sys.version,
              'executable': sys.executable, 'prefix': sys.prefix}
    try:
        expected_prefix = Path(config['environment']).resolve()
        assert Path(sys.prefix).resolve() == expected_prefix, 'Wrong interpreter environment'
        entries = {}
        for group in ('openbexi.backends.v1', 'openbexi.shared_backends.v1'):
            entries[group] = [entry for entry in metadata.entry_points(group=group) if entry.name == 'spell']
        console = [entry for entry in metadata.entry_points(group='console_scripts')
                   if entry.name == 'openbexi-spell-host']
        if config['phase'] == 'removed':
            for name in ('openbexi-spell-host', 'openbexi-spell-shared'):
                try:
                    metadata.distribution(name)
                except metadata.PackageNotFoundError:
                    pass
                else:
                    raise AssertionError('Distribution survived removal: ' + name)
            for name in ('openbexi_spell_host', 'openbexi_spell_shared'):
                assert importlib.util.find_spec(name) is None, 'Module survived removal: ' + name
            assert not any(entries.values()) and not console, 'Plugin entry point survived removal'
            command = expected_prefix / ('Scripts/openbexi-spell-host.exe' if os.name == 'nt' else 'bin/openbexi-spell-host')
            assert not command.exists(), 'Host console command survived removal'
            report['packages_absent'] = True
            report['entry_points_absent'] = True
        else:
            report['packages'] = [installed_wheel(identity) for identity in config['wheels']]
            import openbexi_spell_host as host
            import openbexi_spell_shared as shared
            expected_host = next(item['version'] for item in config['wheels'] if item['name'] == 'openbexi-spell-host')
            assert host.__version__ == expected_host, 'Host module version differs from distribution'
            for module in (host, shared):
                assert Path(module.__file__).resolve().is_relative_to(expected_prefix), 'Imported repository package'
            host_entry, = entries['openbexi.backends.v1']
            shared_entry, = entries['openbexi.shared_backends.v1']
            console_entry, = console
            assert host_entry.value == 'openbexi_spell_host:describe' and host_entry.load() is host.describe
            assert shared_entry.value == 'openbexi_spell_shared:provider' and shared_entry.load() is shared.provider
            assert console_entry.value == 'openbexi_spell_host.runner:main'
            assert host.describe()['id'] == 'spell' and host.describe()['api'] == 1
            assert shared.provider.api == 1
            bindings = json.loads(Path(config['bindings']).read_text(encoding='utf-8'))
            for binding in bindings:
                shared.validate(binding)
            assert shared.VERSION == '0.4.0', 'Durable binding protocol changed during package upgrade'
            report['imports'] = {'host': host.__file__, 'shared': shared.__file__,
                                 'host_module_version': host.__version__, 'shared_binding_protocol': shared.VERSION}
            report['entry_points'] = {group: [entry.value for entry in found] for group, found in entries.items()}
            report['preserved_binding_profiles'] = [binding['profile'] for binding in bindings]
        assert {name: sha(name) for name in config['user_files']} == config['user_files'], 'User files changed'
        import openbexi_upgrade_sentinel
        assert openbexi_upgrade_sentinel.VALUE == 'unrelated user module'
        report['user_files_unchanged'] = True
        report['unrelated_module_preserved'] = True
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    Path(result_path).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'phase': report['phase'], 'passed': report['passed'], 'error': report.get('error')}))
    return 0 if report['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-host', type=Path, required=True)
    parser.add_argument('--old-shared', type=Path, required=True)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--shared', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v06/python-upgrade')
    parser.add_argument('--source-commit', help='Explicit immutable source identity when running outside a Git checkout')
    args = parser.parse_args(argv)
    output = args.output.resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    report = {'passed': False, 'builder_sha256': sha(Path(__file__)), 'commands': [], 'phases': [],
              'scope': 'Installed Python host/shared package upgrade/removal and persisted binding validation only; no native process, driver, IDE workflow, or complete v0.6 acceptance',
              'python': sys.version, 'platform': sys.platform}
    environment = output / 'environment'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    def run(label, command, timeout=120):
        result = subprocess.run(command, capture_output=True, timeout=timeout,
                                env=dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_NO_INDEX='1'))
        log = output / (label + '.log')
        log.write_bytes(result.stdout + result.stderr)
        report['commands'].append({'label': label, 'argv': list(map(str, command)),
                                   'returncode': result.returncode, 'log': str(log), 'sha256': sha(log)})
        result.check_returncode()
        return result.stdout.decode('utf-8').strip()

    try:
        old = [wheel_identity(args.old_host.resolve()), wheel_identity(args.old_shared.resolve())]
        new = [wheel_identity(args.host.resolve()), wheel_identity(args.shared.resolve())]
        assert [item['name'] for item in old] == [item['name'] for item in new] == ['openbexi-spell-host', 'openbexi-spell-shared']
        report['inputs'] = {'previous': old, 'target': new}
        revision = args.source_commit or subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        assert len(revision) == 40 and all(c in '0123456789abcdef' for c in revision), 'Expected a full immutable source identity'
        report['source_base_commit'] = revision
        report['harness_sha256'] = sha(Path(__file__).resolve())
        run('create-environment', [sys.executable, '-I', '-m', 'venv', str(environment)])
        site = Path(run('site-packages', [str(python), '-I', '-c', "import sysconfig; print(sysconfig.get_path('purelib'))"]))
        project = output / 'user-project'
        project.mkdir()
        hello = project / 'hello.py'
        hello.write_text("import openbexi_upgrade_sentinel\nassert openbexi_upgrade_sentinel.VALUE == 'unrelated user module'\nprint('ordinary Python still works')\n", encoding='utf-8')
        preferences = project / 'preferences.json'
        preferences.write_text('{"theme":"dark","arguments":["retained"]}\n', encoding='utf-8')
        sentinel = site / 'openbexi_upgrade_sentinel.py'
        sentinel.write_text("VALUE = 'unrelated user module'\n", encoding='utf-8')
        image = 'sha256:' + 'a' * 64
        bindings = [{'profile': 'spell-native-shared-development/1', 'version': '0.4.0', 'image': image},
                    {'profile': 'spell-native-shared-dss/1', 'version': '0.4.0', 'image': image,
                     'driver': {'url': 'http://127.0.0.1:8080', 'host': '127.0.0.1', 'port': 9982}}]
        bindings.append(dict(bindings[1], profile='spell-native-dss-execution/1', release='b' * 64))
        binding_file = project / 'preserved-bindings.json'
        binding_file.write_text(json.dumps(bindings, indent=2) + '\n', encoding='utf-8')
        user_files = {str(path): sha(path) for path in (hello, preferences, sentinel, binding_file)}
        report['user_files'] = user_files
        pip = [str(python), '-I', '-m', 'pip', '--disable-pip-version-check']
        assert run('ordinary-python-before-install', [str(python), '-I', str(hello)]) == 'ordinary Python still works'
        for phase, wheels in (('previous', old), ('upgraded', new), ('removed', [])):
            if wheels:
                command = pip + ['install', '--no-index', '--no-cache-dir']
                if phase == 'upgraded':
                    command.append('--upgrade')
                command += [item['path'] for item in wheels]
            else:
                command = pip + ['uninstall', '--yes', 'openbexi-spell-shared', 'openbexi-spell-host']
            run(phase + '-pip', command)
            run(phase + '-pip-check', pip + ['check'])
            config = {'phase': phase, 'environment': str(environment), 'wheels': wheels,
                      'user_files': user_files, 'bindings': str(binding_file)}
            config_path, result_path = output / (phase + '-input.json'), output / (phase + '-result.json')
            config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
            run(phase + '-probe', [str(python), '-I', str(Path(__file__).resolve()), '--probe', str(config_path), str(result_path)])
            assert run(phase + '-ordinary-python', [str(python), '-I', str(hello)]) == 'ordinary Python still works'
            report['phases'].append({'phase': phase, 'result': str(result_path), 'sha256': sha(result_path),
                                     'passed': json.loads(result_path.read_text(encoding='utf-8'))['passed']})
        assert all(sha(item['path']) == item['sha256'] for item in old + new), 'Input wheels changed'
        assert {name: sha(name) for name in user_files} == user_files, 'User files changed'
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'output': str(output), 'passed': report['passed'], 'phases': report['phases'], 'error': report.get('error')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--probe':
        raise SystemExit(probe(sys.argv[2], sys.argv[3]))
    raise SystemExit(main())
