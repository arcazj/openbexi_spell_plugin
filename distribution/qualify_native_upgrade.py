"""Qualify installed native/driver package upgrades in an offline Linux image.

Runs an original native Display/DataContainer procedure before and after an
upgrade, preserving the initialized example and user files. This is a package
upgrade gate, not a replacement for native language or IDE workflow gates.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def support():
    # Explicit file loading works under -I without adding source trees to sys.path.
    path = Path(__file__).with_name('qualify_python_upgrade.py')
    spec = importlib.util.spec_from_file_location('upgrade_record_checks', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installed_check(config_path, result_path):
    config = json.loads(Path(config_path).read_text())
    assert Path(sys.prefix) == Path(config['environment']), 'Unexpected interpreter environment'
    checks = support()
    result = {'packages': [checks.installed_wheel(wheel) for wheel in config['wheels']]}
    import spell_native
    import openbexi_spell_dss
    import openbexi_dss_proxy
    result['imports'] = {}
    for module in (spell_native, openbexi_spell_dss, openbexi_dss_proxy):
        assert Path(module.__file__).is_relative_to(sys.prefix), 'Imported a package outside the fresh environment'
        result['imports'][module.__name__] = module.__file__
    entries = {entry.name: entry.value for entry in metadata.entry_points(group='console_scripts')
               if entry.name in {'spell-native', 'spell-native-python', 'openbexi-spell-displays'}}
    assert entries == {'spell-native': 'spell_native.launcher:main',
                       'spell-native-python': 'spell_native.launcher:python_main',
                       'openbexi-spell-displays': 'openbexi_spell_dss.display_viewer:main'}
    result['entry_points'] = entries
    result['passed'] = True
    Path(result_path).write_text(json.dumps(result, indent=2) + '\n')


def inside(config_path):
    config = json.loads(Path(config_path).read_text())
    output = Path('/evidence')
    output.mkdir()
    environment = Path('/opt/native-upgrade')
    python = environment / 'bin/python'
    native = environment / 'bin/spell-native'
    example_root = output / 'example'
    report = {'passed': False, 'commands': [], 'phases': [], 'python': sys.version,
              'scope': 'Original native Display/DataContainer execution and installed package upgrade/removal; no DSS commanding, IDE workflow, or complete release acceptance'}

    def run(label, command, *, env=None, timeout=120):
        result = subprocess.run(list(map(str, command)), capture_output=True, timeout=timeout,
                                env=dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1',
                                         PIP_NO_INDEX='1', **(env or {})))
        log = output / (label + '.log')
        log.write_bytes(result.stdout + result.stderr)
        report['commands'].append({'label': label, 'argv': list(map(str, command)),
                                   'returncode': result.returncode, 'log': str(log), 'sha256': sha(log)})
        result.check_returncode()
        assert b'AddressSanitizer:' not in result.stderr and b'runtime error:' not in result.stderr, 'Native diagnostic failure: ' + label
        return result.stdout.decode('utf-8').strip()

    try:
        assert sys.platform == 'linux' and sys.version_info[:3] == (3, 13, 15)
        for filename, expected in config['scripts'].items():
            assert sha(Path('/tmp') / filename) == expected, 'Qualification script changed'
        compiler_tools = {name: shutil.which(name) for name in ('cc', 'gcc', 'g++', 'c++', 'clang', 'clang++', 'make', 'cmake', 'protoc')}
        assert not any(compiler_tools.values()), 'Compiler/build tool found in runtime image'
        report['compiler_tools'] = compiler_tools
        report['dependency_wheelhouse'] = {path.name: sha(path) for path in sorted(Path('/wheelhouse').glob('*.whl'))}
        assert report['dependency_wheelhouse'], 'Missing offline dependency wheelhouse'
        assert not Path('/source').exists() and not Path('/out').exists(), 'Unexpected build source tree'
        run('create-environment', [sys.executable, '-I', '-m', 'venv', environment])
        procedure = output / 'native-procedure.py'
        procedure.write_text("""import json,sys
from pathlib import Path
import spell,libSPELL_DTA_v3
from spell.runtime import ARGS,IVARS
from spell.lang.functions import Display
assert sys.prefix == '/opt/native-upgrade', sys.prefix
assert Path(spell.__file__).is_relative_to(sys.prefix)
assert Path(libSPELL_DTA_v3.__file__).is_relative_to(sys.prefix)
assert isinstance(ARGS,libSPELL_DTA_v3.DataContainer)
assert isinstance(IVARS,libSPELL_DTA_v3.DataContainer)
assert ARGS['value'] == 21
IVARS['answer'] = ARGS['value'] * 2
assert IVARS['answer'] == 42
Display('NATIVE_UPGRADE_RESULT_42')
Path('/evidence/native-procedure-result.json').write_text(json.dumps({'answer':IVARS['answer'],'prefix':sys.prefix,'native':libSPELL_DTA_v3.__file__}))
""", encoding='utf-8')
        hello = output / 'hello.py'
        hello.write_text("assert 6 * 7 == 42\nprint('ordinary Python still works')\n", encoding='utf-8')
        preferences = output / 'user-preferences.json'
        preferences.write_text('{"theme":"dark","arguments":{"value":21}}\n', encoding='utf-8')
        assert run('ordinary-python-before-install', [python, '-I', hello]) == 'ordinary Python still works'
        pip = [python, '-I', '-m', 'pip', '--disable-pip-version-check']
        user_files = None
        for phase, wheels in (('previous', config['previous']), ('upgraded', config['target'])):
            assert all(sha(item['path']) == item['sha256'] for item in wheels), 'Input wheel changed'
            command = pip + ['install', '--no-index', '--no-cache-dir', '--find-links=/wheelhouse']
            if phase == 'upgraded':
                command.append('--upgrade')
            run(phase + '-pip', command + [item['path'] for item in wheels], timeout=300)
            run(phase + '-pip-check', pip + ['check'])
            doctor = json.loads(run(phase + '-doctor', [native, 'doctor']))
            expected = next(item['version'] for item in wheels if item['name'] == 'openbexi-spell-source')
            assert doctor['version'] == expected and doctor['environment'] == str(environment), 'Doctor package/interpreter mismatch'
            if phase == 'previous':
                example = json.loads(run('init-example', [native, 'init-example', example_root]))
                user_paths = [procedure, hello, preferences, example_root / 'environment.json']
                user_paths.extend(path for path in sorted((example_root / 'config').rglob('*')) if path.is_file())
                user_files = {str(path): sha(path) for path in user_paths}
                report['preserved_user_files'] = user_files
            package_input, package_result = output / (phase + '-package-input.json'), output / (phase + '-packages.json')
            package_input.write_text(json.dumps({'environment': str(environment), 'wheels': wheels}, indent=2) + '\n')
            run(phase + '-record-check', [python, '-I', __file__, '--installed-check', package_input, package_result], timeout=300)
            text = run(phase + '-native', [native, 'run', '-f', procedure, '-c', example['config'],
                                         '-n', 'example', '-g', "{'value':21}"], env=example['environment'])
            assert '[ DISPLAY ] NATIVE_UPGRADE_RESULT_42' in text and '[ STATUS  ] FINISHED' in text, 'Native procedure did not finish'
            executed = json.loads((output / 'native-procedure-result.json').read_text())
            assert executed['answer'] == 42 and executed['prefix'] == str(environment)
            (output / (phase + '-execution.json')).write_text(json.dumps(executed, indent=2) + '\n')
            assert {name: sha(name) for name in user_files} == user_files, 'User/example configuration changed'
            assert run(phase + '-ordinary-python', [python, '-I', hello]) == 'ordinary Python still works'
            report['phases'].append({'phase': phase, 'passed': True, 'doctor': doctor,
                                     'package_record': str(package_result), 'package_record_sha256': sha(package_result),
                                     'native_result': executed, 'same_procedure_sha256': sha(procedure), 'user_files_preserved': True})
        run('remove-packages', pip + ['uninstall', '--yes', 'openbexi-spell-dss', 'openbexi-spell-source'])
        run('removed-pip-check', pip + ['check'])
        removal_code = """import importlib.metadata as m,importlib.util,json
from pathlib import Path
import sys
for name in ('openbexi-spell-source','openbexi-spell-dss'):
    try: m.distribution(name)
    except m.PackageNotFoundError: pass
    else: raise AssertionError(name + ' survived uninstall')
for name in ('spell','spell_native','libSPELL_DTA_v3','openbexi_spell_dss','openbexi_dss_proxy'):
    assert importlib.util.find_spec(name) is None,name
names={'spell-native','spell-native-python','openbexi-spell-displays'}
assert not names.intersection(entry.name for entry in m.entry_points(group='console_scripts'))
assert all(not (Path(sys.prefix)/'bin'/name).exists() for name in names)
print(json.dumps({'packages_absent':True,'modules_absent':True,'entry_points_absent':True}))
"""
        removed = json.loads(run('removed-imports', [python, '-I', '-c', removal_code]))
        assert run('removed-ordinary-python', [python, '-I', hello]) == 'ordinary Python still works'
        assert {name: sha(name) for name in user_files} == user_files, 'User/example configuration changed during uninstall'
        report['phases'].append({'phase': 'removed', 'passed': True, **removed, 'user_files_preserved': True})
        report['passed'] = True
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        # Preserve link identities before exporting this disposable fixture on
        # Windows, where docker cp cannot recreate these Linux symlinks.
        report['example_links'] = {}
        for path in sorted((example_root / 'bin').glob('*')):
            if path.is_symlink():
                report['example_links'][str(path)] = os.readlink(path)
                path.unlink()
        (output / 'native-upgrade.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'passed': report['passed'], 'phases': [item['phase'] for item in report['phases']], 'error': report.get('error')}), flush=True)
    return 0 if report['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-image', required=True)
    parser.add_argument('--runtime-id', required=True)
    parser.add_argument('--old-native', type=Path, required=True)
    parser.add_argument('--old-driver', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v06/native-upgrade')
    args = parser.parse_args(argv)
    identity = uuid.uuid4().hex
    output = args.output.resolve() / identity
    output.mkdir(parents=True)
    container = 'openbexi-native-upgrade-' + identity
    report = {'passed': False, 'container': container, 'runtime': args.runtime_id,
              'network': 'none', 'commands': [], 'builder_sha256': sha(__file__),
              'scope': 'Native/driver package upgrade and removal; full language, DSS, IDE, and release gates remain separate'}
    created = False

    def run(label, command, *, check=True, timeout=120):
        result = subprocess.run(list(map(str, command)), capture_output=True, timeout=timeout)
        path = output / (label + '.log')
        path.write_bytes(result.stdout + result.stderr)
        report['commands'].append({'label': label, 'argv': list(map(str, command)),
                                   'returncode': result.returncode, 'log': str(path), 'sha256': sha(path)})
        if check:
            result.check_returncode()
        return result

    try:
        checks = support()
        previous = [checks.wheel_identity(path.resolve()) for path in (args.old_native, args.old_driver)]
        target = [checks.wheel_identity(path.resolve()) for path in (args.native, args.driver)]
        assert [item['name'] for item in previous] == [item['name'] for item in target] == ['openbexi-spell-source', 'openbexi-spell-dss']
        report['inputs'] = {'previous': previous, 'target': target}
        actual = run('runtime-identity', ['docker', 'image', 'inspect', args.runtime_image, '--format', '{{.Id}}']).stdout.decode().strip()
        assert actual == args.runtime_id, 'Runtime image identity differs'
        scripts = [Path(__file__).resolve(), Path(__file__).with_name('qualify_python_upgrade.py').resolve()]
        config = {'scripts': {path.name: sha(path) for path in scripts}}
        for phase, wheels in (('previous', previous), ('target', target)):
            config[phase] = [dict(item, path='/tmp/' + Path(item['path']).name) for item in wheels]
        config_path = output / 'container-input.json'
        config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8', newline='\n')
        report['container_input_sha256'] = sha(config_path)
        run('create', ['docker', 'create', '--name', container, '--init', '--network=none', '--memory=2g',
                       '--pids-limit=512', args.runtime_id, 'python', '-I', '/tmp/qualify_native_upgrade.py', '--inside', '/tmp/container-input.json'])
        created = True
        for index, path in enumerate(scripts + [config_path] + [Path(item['path']) for item in previous + target]):
            run('copy-input-' + str(index), ['docker', 'cp', path, container + ':/tmp/' + path.name], timeout=300)
        run('qualification', ['docker', 'start', '--attach', container], check=False, timeout=1200)
        state = json.loads(run('container-state', ['docker', 'inspect', container]).stdout)[0]
        report['container_exit_code'] = state['State']['ExitCode']
        report['container_oom_killed'] = state['State']['OOMKilled']
        run('copy-evidence', ['docker', 'cp', container + ':/evidence/.', output / 'evidence'], timeout=300)
        result_path = output / 'evidence/native-upgrade.json'
        result = json.loads(result_path.read_text(encoding='utf-8'))
        report['installed_evidence_sha256'] = sha(result_path)
        assert report['container_exit_code'] == 0 and not report['container_oom_killed'] and result['passed'], result.get('error', 'Container qualification failed')
        assert all(sha(item['path']) == item['sha256'] for item in previous + target), 'Input wheels changed'
        report['passed'] = True
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if created:
            # Keep the stopped, uniquely named test container for review/cleanup.
            report['container_retained'] = True
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'output': str(output), 'passed': report['passed'], 'error': report.get('error')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--inside':
        raise SystemExit(inside(sys.argv[2]))
    if len(sys.argv) == 4 and sys.argv[1] == '--installed-check':
        installed_check(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(main())
