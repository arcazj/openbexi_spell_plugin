"""Build original listener/context/server executables with separate native graphs.

SPDX-License-Identifier: GPL-3.0-or-later
Compilation is evidence only; runtime qualification remains a separate gate.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import sysconfig

source,output=Path('/source'),Path('/out')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((output/'native-build.json').read_text())
executor=json.loads((output/'executor-build.json').read_text())
report={'full_context_qualified':False,'programs':{},
    'executor_build_sha256':sha(output/'executor-build.json'),
    'input_sources':{p.name:sha(p) for p in Path('/context').iterdir() if p.is_file()}}
flags=baseline['flags']
objects={row['unit']:row for row in executor['units'] if row['exit_code']==0}


def compile_unit(name):
    path=source/name
    if name in objects and objects[name]['sha256']==sha(path):
        return dict(objects[name],reused=True)
    obj=output/(name.replace('/','_')+'.o')
    result=subprocess.run(flags+['-c',str(path),'-o',str(obj)],capture_output=True,text=True,timeout=120)
    log=obj.with_suffix('.log');log.write_text(result.stdout+result.stderr)
    return {'unit':name,'sha256':sha(path),'exit_code':result.returncode,
        'object':obj.name,'diagnostic':log.name,'reused':False}


for folder,program in (('context','SPELL_Context'),('listener','SPELL_Listener'),
        ('executor','SPELL_Executor_v3'),('service','SPELL_Service_v3')):
    manifest=source/'src'/folder/'Makefile.am'
    text=manifest.read_text().replace('\\\n',' ')
    assignment=re.findall(r'^'+program+r'_LDADD\s*=\s*([^\n]+)',text,re.M)
    sources=re.findall(r'^'+program+r'_SOURCES\s*=\s*([^\n]+)',text,re.M)
    assert len(assignment)==len(sources)==1
    libraries=re.findall(r'/lib/(SPELL_\w+)/lib\1_v[23]\.la',assignment[0])
    units=[unit for lib in libraries for unit in baseline['library_manifest'][lib]['units']]
    mains=[(manifest.parent/name).relative_to(source).as_posix() for name in sources[0].split()]
    assert len(set(units+mains))==len(units+mains)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(compile_unit,units+mains))
    objects.update({row['unit']:row for row in results if row['exit_code']==0})
    entry={'manifest':manifest.relative_to(source).as_posix(),'manifest_sha256':sha(manifest),
        'libraries':libraries,'units':results,
        'dependency_profile':'upstream v3' if program.endswith('_v3') else 'upstream dependency list using the corresponding v3 library source manifests'}
    report['programs'][program]=entry
    if any(row['exit_code'] for row in results):continue
    executable=output/program.replace('_','-',1)
    # Context's SPELLexecutor class is distinct from EXC's class. Keep these
    # dependency graphs in separate executables, as in the original build.
    link=['c++','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
        *[str(output/row['object']) for row in results],
        '-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13',
        '-llog4cplus','-lxerces-c','-lz','-lmenu','-lncurses','-o',str(executable)]
    # Server/service and imported DTA must share the same executor singleton.
    # The common runtime also contains the automatic/standalone CIF libraries.
    if 'SPELL_EXC' in libraries:
        assert set(libraries).issubset(executor['libraries'])
        link=['c++','-pthread','-fsanitize=address,undefined',
            *[str(output/row['object']) for row in results if row['unit'] in mains],
            '-L/out','-lspell_executor313','-Wl,-rpath,$ORIGIN',
            '-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o',str(executable)]
        entry['shared_runtime']={'sha256':sha(output/'libspell_executor313.so'),
            'libraries':executor['libraries'],'extra_libraries':sorted(set(executor['libraries'])-set(libraries))}
    result=subprocess.run(link,capture_output=True,text=True,timeout=120)
    log=output/(program+'-link.log');log.write_text(result.stdout+result.stderr)
    entry.update(link_exit_code=result.returncode,diagnostic=log.name)
    if result.returncode==0:
        entry.update(executable=executable.name,sha256=sha(executable))

if all(entry.get('link_exit_code')==0 for entry in report['programs'].values()):
    result=subprocess.run(flags+['/context/qualify_service_bindings.cpp','-L/out','-lspell_executor313',
        '-Wl,-rpath,$ORIGIN','-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o','/out/qualify_service_bindings'],
        capture_output=True,text=True,timeout=60)
    (output/'service-bindings-build.log').write_text(result.stdout+result.stderr)
    report['service_bindings_build_exit_code']=result.returncode
    if result.returncode==0:
        result=subprocess.run(['/out/qualify_service_bindings'],capture_output=True,text=True,timeout=30,
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',PYTHONMALLOC='malloc',
                SPELL_HOME='/source',SPELL_DATA='/out/executor-data',SPELL_CONFIG='/out/executor-config'))
        (output/'service-bindings-runtime.log').write_text(result.stdout+result.stderr)
        report['service_bindings_runtime_exit_code']=result.returncode
    result=subprocess.run(flags+['/context/qualify_process.cpp',
        *[str(output/objects[name]['object']) for name in baseline['library_manifest']['SPELL_PRC']['units']],
        '-L/out','-lspell_executor313','-Wl,-rpath,$ORIGIN',
        '-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-llog4cplus','-o','/out/qualify_process'],
        capture_output=True,text=True,timeout=60)
    (output/'process-build.log').write_text(result.stdout+result.stderr)
    report['process_build_exit_code']=result.returncode
    if result.returncode==0:
        result=subprocess.run(['/out/qualify_process'],capture_output=True,text=True,timeout=30,
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
        (output/'process-runtime.log').write_text(result.stdout+result.stderr)
        report['process_runtime_exit_code']=result.returncode
    result=subprocess.run(flags+['/context/server_peer.cpp','-L/out','-lspell_executor313',
        '-Wl,-rpath,$ORIGIN','-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o','/out/server_peer'],
        capture_output=True,text=True,timeout=60)
    (output/'server-peer-build.log').write_text(result.stdout+result.stderr)
    report['server_peer_build_exit_code']=result.returncode
    result=subprocess.run(flags+['/context/controller_peer.cpp','-L/out','-lspell_executor313',
        '-Wl,-rpath,$ORIGIN','-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o','/out/controller_peer'],
        capture_output=True,text=True,timeout=60)
    (output/'controller-peer-build.log').write_text(result.stdout+result.stderr)
    report['controller_peer_build_exit_code']=result.returncode
    result=subprocess.run(flags+['/context/service_recovery_peer.cpp','-L/out','-lspell_executor313',
        '-Wl,-rpath,$ORIGIN','-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o','/out/service_recovery_peer'],
        capture_output=True,text=True,timeout=60)
    (output/'service-recovery-peer-build.log').write_text(result.stdout+result.stderr)
    report['service_recovery_peer_build_exit_code']=result.returncode
    result=subprocess.run(flags+['/context/context_peer.cpp','-L/out','-lspell_executor313',
        '-Wl,-rpath,$ORIGIN','-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o','/out/context_peer'],
        capture_output=True,text=True,timeout=60)
    (output/'context-peer-build.log').write_text(result.stdout+result.stderr)
    report['peer_build_exit_code']=result.returncode
    if result.returncode==0 and report['server_peer_build_exit_code']==0 and report['controller_peer_build_exit_code']==0 and report['service_recovery_peer_build_exit_code']==0:
        result=subprocess.run([sys.executable,'-I','/context/qualify_context.py'],
            capture_output=True,text=True,timeout=360)
        (output/'context-qualification.log').write_text(result.stdout+result.stderr)
        report['qualification_exit_code']=result.returncode
(output/'context-build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({name:{'compile_failures':sum(row['exit_code']!=0 for row in entry['units']),
    'link_exit_code':entry.get('link_exit_code')} for name,entry in report['programs'].items()}))
