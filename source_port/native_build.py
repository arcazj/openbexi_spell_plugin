"""Build/link/load exact-source native UTIL. SPDX-License-Identifier: GPL-3.0-or-later."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import zipfile

from native_patches import apply_tree
from native_manifest import libraries

archive = Path('/input/SPELL2.6.10-src.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
assert sys.version_info[:2] == (3, 13)
source, output = Path('/source'), Path('/out')
source.mkdir()
output.mkdir()
with zipfile.ZipFile(archive) as z:
    assert len(set(z.namelist())) == len(z.namelist()) and z.testzip() is None
    for member in z.infolist():
        target = (source / member.filename).resolve()
        assert target.is_relative_to(source)
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(member))
patches = apply_tree(source)
(output / 'native-patches.json').write_text(json.dumps(patches, indent=2)+'\n')
manifest = libraries(source)
units = sorted(source/p for lib in ('SPELL_UTIL', 'SPELL_SYN') for p in manifest[lib]['units'])
units.append(Path('/input/native/qualify_util.cpp'))
flags = ['c++', '-std=c++17', '-fPIC', '-g', '-O1', '-pthread', '-fmax-errors=8',
         '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
         '-I'+str(source/'include'), '-I'+sysconfig.get_path('include')]


def compile_unit(path):
    stem = path.relative_to(source).as_posix() if path.is_relative_to(source) else path.name
    obj = output / (stem.replace('/', '_')+'.o')
    result = subprocess.run(flags + ['-c', str(path), '-o', str(obj)], capture_output=True, text=True, timeout=120)
    log = obj.with_suffix('.log')
    log.write_text(result.stdout+result.stderr)
    return {'unit':stem, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'exit_code':result.returncode, 'object':obj.name, 'diagnostic':log.name}


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(compile_unit, units))
report = {'python':sys.version, 'platform':platform.platform(), 'flags':flags,
          'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
          'input_sources':{p.relative_to('/input').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(Path('/input').rglob('*'))
                           if p.is_file() and '__pycache__' not in p.parts and p != archive},
          'compiler':subprocess.check_output(['c++','--version'], text=True).splitlines()[0],
          'packages':subprocess.check_output(['dpkg-query','-W','g++','libxerces-c-dev','liblog4cplus-dev','libncurses-dev','zlib1g-dev'],text=True),
          'units':results, 'library_manifest':manifest, 'full_native_qualified':False}
if all(r['exit_code']==0 for r in results):
    extension = output / ('_spell_util_qualification'+sysconfig.get_config_var('EXT_SUFFIX'))
    command = ['c++','-shared','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
               *[str(output/r['object']) for r in results], '-L'+sysconfig.get_config_var('LIBDIR'),
               '-lpython3.13','-llog4cplus','-lz','-o',str(extension)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (output/'link.log').write_text(result.stdout+result.stderr)
    report['link_exit_code'] = result.returncode
    if result.returncode == 0:
        # Load the C++ runtime at process startup so ASan can intercept throws
        # before Python dlopens the C++ extension.
        preload = ':'.join(subprocess.check_output(['c++','-print-file-name='+name],text=True).strip()
                           for name in ('libasan.so', 'libstdc++.so'))
        env = dict(os.environ, LD_PRELOAD=preload,
                   ASAN_OPTIONS='detect_leaks=0:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
                   PYTHONMALLOC='malloc', SPELL_HOME=str(source), SPELL_DATA='/out/data')
        result = subprocess.run([sys.executable,'-I','/input/native/qualify_util.py'],env=env,
                                capture_output=True,text=True,timeout=120)
        (output/'runtime.log').write_text(result.stdout+result.stderr)
        report['runtime_exit_code'] = result.returncode
        program = output/'qualify_embed'
        command = flags + ['/input/native/qualify_embed.cpp',
            *[str(output/r['object']) for r in results if r['unit'] != 'qualify_util.cpp'],
            '-L'+sysconfig.get_config_var('LIBDIR'), '-lpython3.13','-llog4cplus','-lz','-o',str(program)]
        result = subprocess.run(command,capture_output=True,text=True,timeout=120)
        (output/'embed-build.log').write_text(result.stdout+result.stderr)
        report['embed_build_exit_code'] = result.returncode
        if result.returncode == 0:
            result = subprocess.run([str(program)],env=env,capture_output=True,text=True,timeout=120)
            (output/'embed-runtime.log').write_text(result.stdout+result.stderr)
            report['embed_runtime_exit_code'] = result.returncode
            if result.returncode == 0:
                report['embedding'] = json.loads(result.stdout)

        analysis_units = [source/'lib/SPELL_EXC/src'/name for name in ('SPELLastAnalyzer.C','SPELLlnotab.C','SPELLgoto.C','SPELLvariableMonitor.C','SPELLbytecode.C')]
        analysis_units.append(Path('/input/native/qualify_analysis.cpp'))
        with ThreadPoolExecutor(max_workers=4) as pool:
            report['analysis_units'] = list(pool.map(compile_unit, analysis_units))
        if all(r['exit_code'] == 0 for r in report['analysis_units']):
            extension = output/('_spell_analysis_qualification'+sysconfig.get_config_var('EXT_SUFFIX'))
            objects = [r for r in results if r['unit'] != 'qualify_util.cpp'] + report['analysis_units']
            result = subprocess.run(['c++','-shared','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
                *[str(output/r['object']) for r in objects], '-L'+sysconfig.get_config_var('LIBDIR'),
                '-lpython3.13','-llog4cplus','-lz','-o',str(extension)], capture_output=True,text=True,timeout=120)
            (output/'analysis-link.log').write_text(result.stdout+result.stderr)
            report['analysis_link_exit_code'] = result.returncode
            if result.returncode == 0:
                result = subprocess.run([sys.executable,'-I','/input/native/qualify_analysis.py'],env=env,
                    capture_output=True,text=True,timeout=120)
                (output/'analysis-runtime.log').write_text(result.stdout+result.stderr)
                report['analysis_runtime_exit_code'] = result.returncode

        storage_units = [source/'lib/SPELL_WS/src/SPELLwsStorage.C',Path('/input/native/qualify_storage.cpp')]
        with ThreadPoolExecutor(max_workers=4) as pool:
            report['storage_units'] = list(pool.map(compile_unit, storage_units))
        if all(r['exit_code'] == 0 for r in report['storage_units']):
            extension = output/('_spell_storage_qualification'+sysconfig.get_config_var('EXT_SUFFIX'))
            objects = [r for r in results if r['unit'] != 'qualify_util.cpp'] + report['storage_units']
            result = subprocess.run(['c++','-shared','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
                *[str(output/r['object']) for r in objects], '-L'+sysconfig.get_config_var('LIBDIR'),
                '-lpython3.13','-llog4cplus','-lz','-o',str(extension)],capture_output=True,text=True,timeout=120)
            (output/'storage-link.log').write_text(result.stdout+result.stderr)
            report['storage_link_exit_code'] = result.returncode
            if result.returncode == 0:
                result = subprocess.run([sys.executable,'-I','/input/native/qualify_storage.py'],env=env,
                    capture_output=True,text=True,timeout=120)
                (output/'storage-runtime.log').write_text(result.stdout+result.stderr)
                report['storage_runtime_exit_code'] = result.returncode

def syntax_unit(path):
    stem = path.relative_to(source).as_posix()
    log = output/(stem.replace('/','_')+'.syntax.log')
    result = subprocess.run(flags+['-fsyntax-only',str(path)],capture_output=True,text=True,timeout=60)
    log.write_text(result.stdout+result.stderr)
    return {'unit':stem,'exit_code':result.returncode,'diagnostic':log.name}

downstream = sorted(source/p for lib in ('SPELL_DTA','SPELL_EXC','SPELL_WS') for p in manifest[lib]['units'])
with ThreadPoolExecutor(max_workers=4) as pool:
    report['downstream_syntax'] = list(pool.map(syntax_unit, downstream))
remaining = sorted(source/p for lib in manifest for p in manifest[lib]['units'] if source/p not in units and source/p not in downstream)
with ThreadPoolExecutor(max_workers=4) as pool:
    report['remaining_library_syntax'] = list(pool.map(syntax_unit, remaining))
(output/'native-build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'compiled':sum(r['exit_code']==0 for r in results), 'units':len(results),
                  'link':report.get('link_exit_code'), 'runtime':report.get('runtime_exit_code')}))
# Always export diagnostic evidence; release qualification checks the report.
