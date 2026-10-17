"""Package the qualified original native build for an isolated Linux environment.

SPDX-License-Identifier: GPL-3.0-or-later
This diagnostic foundation includes the ASan/UBSan runtime. Operational release
qualification remains separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

VERSION = '0.6.0'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def build(output, evidence, source, recipe, integrated=False):
    output.mkdir(parents=True, exist_ok=False)
    # Reuse the independent recorder's complete gate, including current inputs.
    subprocess.run([sys.executable, str(recipe / 'record_native.py'),
                    '--evidence', str(evidence), '--service-recovery-policy'], check=True)
    accepted = recipe.parent / 'docs/NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json'
    report = json.loads(accepted.read_text())
    if integrated and (not report['build'].get('composition')
                       or not report['executor_build'].get('composition')):
        raise ValueError('Integrated wheel requires both composed native and Python qualification')
    if integrated:
        context = report['context_build']
        if (context.get('ipc_error_routing_build_exit_code') != 0
                or context.get('ipc_error_routing_runtime_exit_code') != 0):
            raise ValueError('Integrated wheel requires the native IPC error collision probe')
        diagnostic = (evidence/'ipc-error-routing-runtime.log').read_text()
        for marker in ('CORRELATED_STATUS_RESPONSES 16/16', 'ASYNC_ERROR_NOTIFICATIONS 16/16',
                       'SYNCHRONOUS_ERROR_RESPONSE 1', 'UNEXPECTED_NOTIFICATIONS 0'):
            if marker not in diagnostic:
                raise ValueError('Missing native IPC error routing evidence: '+marker)
    package = output / 'src'
    package.mkdir()
    site = Path(sysconfig.get_path('purelib'))
    shutil.copytree(site / 'spell', package / 'spell', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    runtime = package / 'spell_native'
    runtime.mkdir()
    (runtime / '__init__.py').write_text('# SPDX-License-Identifier: GPL-3.0-or-later\n')
    shutil.copyfile(recipe / 'distribution/launcher.py', runtime / 'launcher.py')
    shutil.copyfile(recipe / 'distribution/library.py', runtime / 'library.py')
    shutil.copyfile(recipe / 'distribution/libSPELL_DTA_v3.py', package / 'libSPELL_DTA_v3.py')
    native = runtime / 'bin'
    native.mkdir()
    names = ['libspell_executor313.so', 'SPELL-ExecutorCmd_v3']
    names.extend(item['executable'] for item in report['context_build']['programs'].values())
    native_hashes = {}
    for name in names:
        artifact = evidence / name
        assert sha(artifact) == report['artifacts'][name]['sha256'], name
        shutil.copyfile(artifact, native / name)
        (native / name).chmod(0o755)
        native_hashes[name] = sha(artifact)
    example = runtime / 'example'
    example.mkdir()
    for original, target in [('config/spell/language.xml', 'language.xml'),
                             ('config/server/server_example.xml', 'server.xml'),
                             ('config/contexts/context_example.xml', 'context.xml'),
                             ('drivers/example/config/driver_example.xml', 'driver.xml')]:
        shutil.copyfile(source / original, example / target)
    # These are the eight import-only adaptations already qualified by the
    # standalone executor, accompanied by preimage/output identities.
    shutil.copytree(evidence / 'executor-drivers', example / 'drivers',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(evidence / 'executor-example-driver-patches.json', example / 'driver-patches.json')
    provenance = runtime / 'provenance'
    provenance.mkdir()
    shutil.copyfile(recipe.parent / 'docs/reference/SPELL2.6.10-src.zip', provenance / 'SPELL2.6.10-src.zip')
    shutil.copytree(recipe, provenance / 'source_port',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(accepted, provenance / 'NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json')
    compositions = {}
    if integrated:
        for kind, build_report in (('native', report['build']), ('python', report['executor_build'])):
            directory = evidence/('integrated-' + kind)
            recorded = json.loads((directory/'manifest.json').read_text())
            if recorded != build_report['composition']:
                raise ValueError('Composition evidence differs from qualified build: ' + kind)
            for name, row in recorded['sources'].items():
                actual = source/name if kind == 'native' else package/name
                if sha(actual) != row['patched_sha256']:
                    raise ValueError('Packaged composition source differs: ' + name)
            shutil.copytree(directory, provenance/('integrated-' + kind))
            compositions[kind] = {'manifest_sha256':sha(directory/'manifest.json'), **recorded}
    for name, original in [('GPL-3.0.txt', source / 'LICENSE'), ('LGPL-3.0.txt', recipe / 'LGPL-3.0.txt')]:
        shutil.copyfile(original, output / name)
    manifest = {'version': VERSION, 'profile': 'ASan/UBSan diagnostic native foundation',
                'platform': 'Linux x86_64; pinned Debian Python image; GIL CPython 3.13.15',
                'archive_sha256': report['build']['archive_sha256'],
                'compiler': report['build']['compiler'], 'packages': report['build']['packages'],
                'qualification_sha256': sha(accepted), 'native_artifacts': native_hashes,
                'python_sources': {p.relative_to(package).as_posix(): sha(p) for p in sorted((package / 'spell').rglob('*.py'))},
                'inputs': {p.relative_to(recipe).as_posix(): sha(p) for p in sorted(recipe.rglob('*'))
                           if p.is_file() and '__pycache__' not in p.parts},
                'release_scope': 'Original native foundation; full language conformance remains separate'}
    if integrated:
        manifest['composition'] = compositions
    (runtime / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'pyproject.toml').write_text('''[build-system]
requires = ["setuptools==80.9.0"]
build-backend = "setuptools.build_meta"
[project]
name = "openbexi-spell-source"
version = "@VERSION@"
description = "Original-source SPELL native diagnostic runtime for isolated CPython 3.13.15"
requires-python = "==3.13.15"
license = "GPL-3.0-or-later AND LGPL-3.0-or-later"
license-files = ["GPL-3.0.txt", "LGPL-3.0.txt"]
dependencies = ["grpcio==1.84.0", "protobuf==7.36.2", "cloudpickle==3.1.2", "typing_extensions==4.16.0"]
[project.scripts]
spell-native = "spell_native.launcher:main"
spell-native-python = "spell_native.launcher:python_main"
[tool.setuptools]
package-dir = {"" = "src"}
py-modules = ["libSPELL_DTA_v3"]
[tool.setuptools.packages.find]
where = ["src"]
namespaces = false
[tool.setuptools.package-data]
spell_native = ["**/*"]
'''.replace('@VERSION@', VERSION))
    (output / 'setup.py').write_text('''from setuptools import setup, Distribution
class NativeDistribution(Distribution):
    def has_ext_modules(self): return True
setup(distclass=NativeDistribution)
''')
    env = dict(os.environ, SOURCE_DATE_EPOCH='1791676800')
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-build-isolation', '--no-deps',
                    '--wheel-dir', str(output / 'wheels'), str(output)], env=env, check=True)
    wheel, = (output / 'wheels').glob('*.whl')
    assert wheel.name.endswith('-cp313-cp313-linux_x86_64.whl'), wheel.name
    result = {'wheel': wheel.name, 'sha256': sha(wheel), 'manifest': manifest}
    (output / 'package-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return wheel


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=Path('/out'))
    parser.add_argument('--source', type=Path, default=Path('/source'))
    parser.add_argument('--integrated', action='store_true', help='Require the complete qualified composition inside the wheel')
    args = parser.parse_args()
    print(build(args.output.resolve(), args.evidence.resolve(), args.source.resolve(), Path(__file__).resolve().parent, args.integrated))
