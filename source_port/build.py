"""Build the isolated original-source Python/RPC foundation wheel.

SPDX-License-Identifier: GPL-3.0-or-later
Run from a dedicated CPython 3.13 build environment with source_port/build.lock.
The output must be a new directory. Never install this wheel beside the bounded
openbexi-spell-plugin alias: both provide the upstream `spell` namespace.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

from patches import apply, PREIMAGES

ARCHIVE_SHA256 = '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
VERSION = '0.2.0a1'
TOOLS = {'setuptools': '80.9.0', 'grpcio-tools': '1.84.0', 'grpcio': '1.84.0', 'protobuf': '7.36.2'}
SCHEMAS = ('SPELLDriver', 'SPELLExecutor', 'SPELLService')
sha = lambda data: hashlib.sha256(data).hexdigest()


def prepare(archive, output, recipe_root):
    data = archive.read_bytes()
    if sha(data) != ARCHIVE_SHA256:
        raise ValueError('Archive SHA-256 differs from the supplied source authority')
    recipe = ('build.py', 'patches.py', 'qualify.py', 'build.lock', 'runtime.lock', 'README.md', 'LGPL-3.0.txt')
    for file in recipe:
        if not (recipe_root / file).is_file():
            raise ValueError('Missing build material: ' + file)
    output.mkdir(parents=True, exist_ok=False)
    package = output / 'src'
    sources, modified, schema_hashes = {}, {}, {}
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or z.testzip() is not None:
            raise ValueError('Invalid or duplicate archive member')
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe source member: ' + name)
            if not name.startswith('src/spell/spell/') or not name.endswith('.py'):
                continue
            relative = name.removeprefix('src/spell/')
            original = z.read(name)
            patched = apply(relative, original)
            target = package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(patched)
            sources[name] = {'original_sha256': sha(original), 'wheel_path': relative, 'sha256': sha(patched)}
            if patched != original:
                modified[relative] = {'original_sha256': sha(original), 'patched_sha256': sha(patched)}
        assert set(modified) == set(PREIMAGES)
        proto = output / 'protos'
        proto.mkdir()
        for schema in SCHEMAS:
            original = z.read('protos/' + schema + '.proto')
            (proto / (schema + '.proto')).write_bytes(original)
            schema_hashes[schema + '.proto'] = sha(original)
    stubs = package / 'spell/stubs'
    stubs.mkdir()
    (stubs / '__init__.py').write_text('# Generated RPC package; SPDX-License-Identifier: GPL-3.0-or-later\n', encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'grpc_tools.protoc', '-I' + str(proto),
        '--python_out=' + str(stubs), '--grpc_python_out=' + str(stubs),
        *[str(proto / (schema + '.proto')) for schema in SCHEMAS]], check=True)
    generated = {}
    for path in sorted(stubs.glob('*.py')):
        text = path.read_text(encoding='utf-8')
        original = text
        for schema in SCHEMAS:
            text = text.replace('import ' + schema + '_pb2 as ', 'from spell.stubs import ' + schema + '_pb2 as ')
        path.write_text(text, encoding='utf-8', newline='\n')
        generated[path.relative_to(package).as_posix()] = {
            'protoc_sha256': sha(original.encode()), 'sha256': sha(path.read_bytes()),
            'namespace_import_adapted': text != original}
    manifest = {'distribution': 'openbexi-spell-source', 'version': VERSION, 'upstream': 'SPELL 2.6.10',
        'archive_sha256': ARCHIVE_SHA256, 'tools': TOOLS, 'sources': sources, 'patches': modified,
        'schemas': schema_hashes, 'generated': generated,
        'scope': 'original Python modules, RPC schema and driver-framework foundation; native executor unavailable',
        'unsupported': ['native DTA/EXC/UTIL/WS', 'Step/Goto/warm-start', 'operational Execution', 'JetBrains host plugins'],
        'namespace': 'spell; isolated environment required, incompatible with the bounded alias in one interpreter'}
    provenance = package / 'spell_source_provenance'
    provenance.mkdir()
    (provenance / '__init__.py').write_text('# Source/recipe evidence; SPDX-License-Identifier: GPL-3.0-or-later\n', encoding='utf-8')
    (provenance / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    # Corresponding sources and exact recipe travel with this separate GPL wheel.
    (provenance / archive.name).write_bytes(data)
    for file in recipe:
        (provenance / file).write_bytes((recipe_root / file).read_bytes())
    with zipfile.ZipFile(archive) as z:
        (output / 'GPL-3.0.txt').write_bytes(z.read('LICENSE'))
    (output / 'LGPL-3.0.txt').write_bytes((recipe_root / 'LGPL-3.0.txt').read_bytes())
    (output / 'README.md').write_bytes((recipe_root / 'README.md').read_bytes())
    (output / 'pyproject.toml').write_text('''[build-system]
requires = ["setuptools==80.9.0"]
build-backend = "setuptools.build_meta"
[project]
name = "openbexi-spell-source"
version = "0.2.0a1"
description = "Isolated original SPELL Python/RPC foundation; native executor pending"
readme = "README.md"
requires-python = ">=3.13,<3.14"
license = "GPL-3.0-or-later AND LGPL-3.0-or-later"
license-files = ["GPL-3.0.txt", "LGPL-3.0.txt"]
dependencies = ["grpcio==1.84.0", "protobuf==7.36.2"]
[tool.setuptools.packages.find]
where = ["src"]
namespaces = false
[tool.setuptools.package-data]
spell_source_provenance = ["*.json", "*.zip", "*.lock", "*.md", "*.txt"]
''', encoding='utf-8', newline='\n')
    for path in package.rglob('*.py'):
        compile(path.read_bytes(), str(path), 'exec')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 13):
        parser.error('Use CPython 3.13')
    for tool, expected in TOOLS.items():
        if version(tool) != expected:
            parser.error('Build environment mismatch: ' + tool)
    recipe_root = Path(__file__).resolve().parent
    embedded_archive = recipe_root / 'SPELL2.6.10-src.zip'
    archive = args.archive or (embedded_archive if embedded_archive.is_file() else
        recipe_root.parent / 'docs/reference/SPELL2.6.10-src.zip')
    output = args.output.resolve()
    manifest = prepare(archive, output, recipe_root)
    env = dict(os.environ, SOURCE_DATE_EPOCH='1791676800')
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-build-isolation', '--no-deps',
        '--wheel-dir', str(output / 'wheels'), str(output)], env=env, check=True)
    wheel = next((output / 'wheels').glob('*.whl'))
    (output / 'build-result.json').write_text(json.dumps({'wheel': wheel.name, 'sha256': sha(wheel.read_bytes()),
        'original_modules': len(manifest['sources']), 'patched_modules':len(manifest['patches']),
        'rpc_schemas':len(SCHEMAS), 'native_supported':False},indent=2)+'\n',encoding='utf-8')
    print((output / 'build-result.json').read_text())


if __name__ == '__main__':
    main()
