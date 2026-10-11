"""Compile against the exact headers shipped with the accepted native wheel."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import sysconfig
import zipfile
import spell_native

root = Path(spell_native.__file__).parent
recipe = root / 'provenance/source_port'
sys.path.insert(0, str(recipe))
from native_patches import apply_tree

source = Path('/tmp/bridge-source')
source.mkdir()
with zipfile.ZipFile(root / 'provenance/SPELL2.6.10-src.zip') as archive:
    for item in archive.infolist():
        path = (source / item.filename).resolve()
        assert path.is_relative_to(source)
        if not item.is_dir():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(item))
apply_tree(source)
fields = set()
for header in (source / 'include/SPELL_IPC').glob('*.H'):
    fields.update(re.findall(r'FIELD_\w+\s*\(\s*"([^"]+)"\s*\)', header.read_text()))
assert {'Csp', 'ExecutorStatus', 'VarName', 'VarValue', 'ContextPort'} <= fields
Path('/bridge/fields.inc').write_text('static const char* fieldNames[] = {\n' +
    ',\n'.join(json.dumps(field) for field in sorted(fields)) + '\n};\n')
subprocess.run(['c++', '-std=c++17', '-g', '-O1', '-pthread',
    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
    '-I' + str(source / 'include'), '-I' + sysconfig.get_path('include'),
    '/bridge/native_bridge.cpp', '-L' + str(root / 'bin'), '-lspell_executor313',
    '-Wl,-rpath,' + str(root / 'bin'), '-L/usr/local/lib', '-lpython3.13',
    '-o', '/bridge/spell-host-ipc'], check=True)
Path('/bridge/build.json').write_text(json.dumps({
    'protocol': 1, 'native_version': metadata.version('openbexi-spell-source'),
    'bridge_sha256': hashlib.sha256(Path('/bridge/spell-host-ipc').read_bytes()).hexdigest(),
    'fields': sorted(fields),
    'packages': subprocess.check_output(['dpkg-query', '-W', 'g++', 'nlohmann-json3-dev'], text=True),
}, indent=2) + '\n')
