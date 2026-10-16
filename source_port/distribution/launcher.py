"""Installed original-source native runtime entry points.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import ctypes.util
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import sysconfig
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROGRAMS = {'run': 'SPELL-ExecutorCmd_v3', 'server': 'SPELL-Executor_v3',
            'listener': 'SPELL-Listener', 'context': 'SPELL-Context',
            'service': 'SPELL-Service_v3'}


def validate():
    if (platform.python_implementation() != 'CPython' or
            sys.version_info[:3] != (3, 13, 15) or
            sysconfig.get_config_var('Py_GIL_DISABLED') or
            sys.platform != 'linux' or platform.machine() != 'x86_64'):
        raise SystemExit('This diagnostic native package requires Linux x86_64, GIL-enabled CPython 3.13.15.')
    try:
        metadata.distribution('openbexi-spell-plugin')
    except metadata.PackageNotFoundError:
        pass
    else:
        raise SystemExit('Install the original-source runtime in a separate environment from the bounded SPELL alias.')


def environment():
    validate()
    from .library import priorities
    try:
        ordering=priorities(os.environ.get('OPENBEXI_SPELL_PROJECT',os.getcwd()))
    except (OSError,ValueError) as error:
        raise SystemExit('Invalid spell-library.json: '+str(error)) from error
    return dict(os.environ, OPENBEXI_SPELL_PYTHON=sys.executable,
                OPENBEXI_SPELL_LIBRARY_PRIORITIES=ordering,
                ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', PYTHONMALLOC='malloc')


def init_example(destination):
    """Install an explicitly selected local example, using the upstream driver."""
    target = Path(destination).absolute()
    # Fail before writing if anything already exists at the chosen destination.
    target.mkdir(parents=True, exist_ok=False)
    for directory in ('bin', 'config/spell', 'config/server', 'config/contexts',
                      'data/Procedures', 'data/UserLib', 'data/Runtime',
                      'data/SpacecraftDB', 'data/GroundDB', 'data/OutputFiles/AsRun',
                      'data/OutputFiles/Warmstart', 'logs'):
        (target / directory).mkdir(parents=True, exist_ok=True)
    example = ROOT / 'example'
    # The original context appends _v3 for Python 3 procedure metadata. Both
    # local names intentionally select this package's sole CPython 3 runtime.
    for name in ('SPELL-Executor', 'SPELL-Executor_v3'):
        (target / 'bin' / name).symlink_to(ROOT / 'bin/SPELL-Executor_v3')
    shutil.copytree(example / 'drivers', target / 'drivers')
    shutil.copyfile(example / 'language.xml', target / 'config/spell/language.xml')
    server = ET.parse(example / 'server.xml')
    server.find("./context/property[@name='ExecutorProgram']").text = str(target / 'bin/SPELL-Executor')
    ET.SubElement(server.getroot().find('context'), 'property', name='ServiceProgram').text = str(ROOT / 'bin/SPELL-Service_v3')
    server.write(target / 'config/server/server.xml', encoding='utf-8')
    context = ET.parse(example / 'context.xml')
    ET.SubElement(context.getroot().find('driverconfig'), 'property', name='CWS').text = 'DSS'
    databases = context.getroot().find('databases')
    for datasource in list(databases.findall('datasource')):
        databases.remove(datasource)
    context.write(target / 'config/contexts/context_example.xml', encoding='utf-8')
    driver = ET.parse(example / 'driver.xml')
    driver.getroot().find('path').text = str(target / 'drivers')
    driver.write(target / 'config/spell/driver_example.xml', encoding='utf-8')
    for directory, name in (('SpacecraftDB', 'SCDB'), ('GroundDB', 'GDB')):
        (target / 'data' / directory / (name + '.DB')).write_text('# Local example database\n', encoding='utf-8')
    settings = {'SPELL_HOME': str(ROOT), 'SPELL_DATA': str(target / 'data'),
                'SPELL_CONFIG': str(target / 'config'), 'SPELL_LOG': str(target / 'logs')}
    (target / 'environment.json').write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'example': str(target), 'environment': settings,
                      'config': str(target / 'config/server/server.xml'),
                      'driver_scope': 'Original local example driver; operational DSS integration is separate.'}))


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print('spell-native {run|server|listener|context|service} [original native options]\n'
              'spell-native init-example NEW_DIRECTORY\nspell-native doctor')
        return
    env = environment()
    mode, *arguments = args
    if mode == 'doctor':
        if arguments:
            raise SystemExit('doctor takes no arguments')
        print(json.dumps({'version': metadata.version('openbexi-spell-source'),
                          'python': sys.version.split()[0], 'environment': sys.prefix,
                          'native_root': str(ROOT), 'profile': 'ASan/UBSan diagnostic',
                          'executables': sorted(PROGRAMS)}))
        return
    if mode == 'init-example':
        if len(arguments) != 1:
            raise SystemExit('init-example requires one new directory')
        init_example(arguments[0])
        return
    if mode not in PROGRAMS:
        raise SystemExit('Unknown native command: ' + mode)
    program = ROOT / 'bin' / PROGRAMS[mode]
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    os.execve(program, [str(program), *arguments], env)


def python_main():
    env = environment()
    libraries = [ctypes.util.find_library(name) for name in ('asan', 'stdc++')]
    if not all(libraries):
        raise SystemExit('The diagnostic runtime requires libasan and libstdc++. See the package platform manifest.')
    env['LD_PRELOAD'] = ':'.join(libraries + ([env['LD_PRELOAD']] if env.get('LD_PRELOAD') else []))
    os.execve(sys.executable, [sys.executable, *sys.argv[1:]], env)
