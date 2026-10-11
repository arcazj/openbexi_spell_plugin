"""Link the original standalone executor and its original library manifest.

SPDX-License-Identifier: GPL-3.0-or-later
Build diagnostics are exported even on failure; the recorder gates promotion.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig

from patches import apply

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source, output = Path('/source'), Path('/out')
baseline = json.loads((output/'native-build.json').read_text())
if 'analysis_units' not in baseline or 'dta_units' not in baseline:
    (output/'executor-build.json').write_text(json.dumps({
        'full_executor_qualified':False,'blocked_by':'native component build failed',
        'native_build_sha256':sha(output/'native-build.json')},indent=2)+'\n')
    for row in baseline['units']:
        if row['exit_code']:
            print((output/row['diagnostic']).read_text())
    sys.exit(0)
manifest = source/'src/executorcmd/Makefile.am'
logical = manifest.read_text().replace('\\\n',' ')
assignment = re.findall(r'^SPELL_ExecutorCmd_v3_LDADD\s*=\s*([^\n]+)',logical,re.M)
assert len(assignment) == 1
libraries = re.findall(r'/lib/(SPELL_\w+)/lib\1_v3.la',assignment[0])
assert len(libraries) == 13 and len(set(libraries)) == 13
units = [p for lib in libraries for p in baseline['library_manifest'][lib]['units']]
assert len(set(units)) == len(units)
compiled = {r['unit']:r for field in ('units','analysis_units','dta_units')
            for r in baseline[field] if r['exit_code'] == 0}
flags = baseline['flags']


def compile_unit(name):
    path = source/name
    if name in compiled and compiled[name]['sha256'] == sha(path):
        return dict(compiled[name], reused=True)
    obj = output/(name.replace('/','_')+'.o')
    result = subprocess.run(flags+['-c',str(path),'-o',str(obj)],capture_output=True,text=True,timeout=120)
    log = obj.with_suffix('.log')
    log.write_text(result.stdout+result.stderr)
    return {'unit':name,'sha256':sha(path),'exit_code':result.returncode,
            'object':obj.name,'diagnostic':log.name,'reused':False}


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(compile_unit,units))
report = {'manifest':manifest.relative_to(source).as_posix(),'manifest_sha256':sha(manifest),
    'libraries':libraries,'units':results,'native_build_sha256':sha(output/'native-build.json'),
    'input_sources':{p.name:sha(p) for p in sorted(Path('/executor').iterdir()) if p.is_file()},
    'full_executor_qualified':False}
if all(r['exit_code'] == 0 for r in results):
    # One shared runtime owns the singleton executor and the DTA module. Importing
    # DTA must not load the separate component-qualification singleton graph.
    runtime = output/'libspell_executor313.so'
    extra = [compiled[n] for n in ('ws_filter.cpp','continuation.cpp')]
    link = ['c++','-shared','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
        *[str(output/r['object']) for r in results+extra],'-L'+sysconfig.get_config_var('LIBDIR'),
        '-lpython3.13','-llog4cplus','-lxerces-c','-lz','-lmenu','-lncurses','-o',str(runtime)]
    result = subprocess.run(link,capture_output=True,text=True,timeout=120)
    (output/'executor-library-link.log').write_text(result.stdout+result.stderr)
    report['library_link_exit_code'] = result.returncode
    if result.returncode == 0:
        command = source/'src/executorcmd/src/SPELLexecutorMain.C'
        executable = output/'SPELL-ExecutorCmd_v3'
        result = subprocess.run(flags+[str(command),'-L/out','-lspell_executor313','-Wl,-rpath,$ORIGIN',
            '-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o',str(executable)],
            capture_output=True,text=True,timeout=120)
        (output/'executor-command-link.log').write_text(result.stdout+result.stderr)
        report['command'] = {'source_sha256':sha(command),'link_exit_code':result.returncode}
        if result.returncode == 0:
            report['command']['sha256'] = sha(executable)
            report['runtime_sha256'] = sha(runtime)
            site = Path(sysconfig.get_path('purelib'))
            python_sources = {}
            for path in sorted((source/'src/spell/spell').rglob('*.py')):
                name = path.relative_to(source/'src/spell').as_posix()
                patched = apply(name,path.read_bytes())
                target = site/name
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(patched)
                python_sources[name] = {'original_sha256':sha(path),'sha256':sha(target)}
            report['python_sources'] = python_sources
            stubs = site/'spell/stubs'
            stubs.mkdir()
            (stubs/'__init__.py').write_text('# Generated original RPC schema package.\n')
            schemas = ('SPELLDriver','SPELLExecutor','SPELLService')
            subprocess.run([sys.executable,'-m','grpc_tools.protoc','-I/source/protos',
                '--python_out='+str(stubs),'--grpc_python_out='+str(stubs),
                *[str(source/'protos'/(name+'.proto')) for name in schemas]],check=True)
            for path in stubs.glob('*.py'):
                text = path.read_text()
                for name in schemas:
                    text = text.replace('import '+name+'_pb2 as ','from spell.stubs import '+name+'_pb2 as ')
                path.write_text(text)
            report['generated_rpc_sources'] = {p.name:sha(p) for p in sorted(stubs.glob('*.py'))}
            (site/'libSPELL_DTA_v3.so').symlink_to(runtime)
            env = dict(os.environ,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',PYTHONMALLOC='malloc',
                SPELL_HOME='/source',SPELL_DATA='/out/executor-data',SPELL_CONFIG='/out/executor-config')
            program = output/'qualify_bindings'
            result = subprocess.run(flags+['/input/native/qualify_bindings.cpp','-L/out','-lspell_executor313',
                '-Wl,-rpath,$ORIGIN','-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o',str(program)],
                capture_output=True,text=True,timeout=120)
            (output/'bindings-embed-build.log').write_text(result.stdout+result.stderr)
            report['bindings_build_exit_code'] = result.returncode
            if result.returncode == 0:
                result = subprocess.run([str(program)],env=env,capture_output=True,text=True,timeout=60)
                (output/'bindings-embed-runtime.log').write_text(result.stdout+result.stderr)
                report['bindings_runtime_exit_code'] = result.returncode
                result = subprocess.run([str(program),'--framework'],env=env,capture_output=True,text=True,timeout=60)
                (output/'bindings-framework-runtime.log').write_text(result.stdout+result.stderr)
                report['bindings_framework_exit_code'] = result.returncode
            result = subprocess.run([sys.executable,'-I','/executor/qualify_executor.py'],env=env,
                capture_output=True,text=True,timeout=180)
            (output/'executor-qualification.log').write_text(result.stdout+result.stderr)
            report['qualification_exit_code'] = result.returncode
(output/'executor-build.json').write_text(json.dumps(report,indent=2)+'\n')
