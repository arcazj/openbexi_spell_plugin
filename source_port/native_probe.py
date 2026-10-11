"""Compile original native units against CPython 3.13 without executing them.

SPDX-License-Identifier: GPL-3.0-or-later
This diagnostic uses the original C++/headers unchanged. It is a syntax probe,
not a link/load test or native compatibility qualification.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import zipfile

archive = Path('/input/SPELL2.6.10-src.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
assert sys.version_info[:2] == (3, 13)
source = Path('/source')
output = Path('/out')
source.mkdir()
output.mkdir()
with zipfile.ZipFile(archive) as z:
    for member in z.infolist():
        path = (source / member.filename).resolve()
        assert path.is_relative_to(source)
        if member.is_dir():
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(member))
libraries = ('SPELL_DTA', 'SPELL_UTIL', 'SPELL_EXC', 'SPELL_WS')
units = sorted(p for lib in libraries for p in (source / 'lib' / lib).rglob('*.C'))
flags = ['c++', '-std=c++17', '-fsyntax-only', '-pthread', '-fmax-errors=8',
    '-I' + str(source / 'include'), '-I' + sysconfig.get_path('include')]


def compile_unit(path):
    result = subprocess.run(flags + [str(path)], capture_output=True, text=True, timeout=60)
    diagnostic = result.stdout + result.stderr
    relative = path.relative_to(source).as_posix()
    log = output / (relative.replace('/', '_') + '.log')
    log.write_text(diagnostic, encoding='utf-8')
    return {'unit': relative, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'exit_code':result.returncode, 'diagnostic':log.name, 'sha256':hashlib.sha256(log.read_bytes()).hexdigest()}


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(compile_unit, units))
manifest = {'python':sys.version, 'platform':platform.platform(),
    'compiler':subprocess.check_output(['c++','--version'],text=True).splitlines()[0],
    'packages':subprocess.check_output(['dpkg-query','-W','g++','libxerces-c-dev','liblog4cplus-dev','zlib1g-dev'],text=True),
    'flags':flags, 'libraries':libraries, 'units':results, 'syntax_only':True, 'native_qualified':False,
    'passed_units':sum(r['exit_code']==0 for r in results), 'failed_units':sum(r['exit_code']!=0 for r in results)}
(output / 'native-probe.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:manifest[key] for key in ('compiler','passed_units','failed_units','syntax_only','native_qualified')}))
