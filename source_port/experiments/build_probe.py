"""Export diagnostics for isolated recovery research. SPDX-License-Identifier: GPL-3.0-or-later."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

out = Path('/out')
out.mkdir(exist_ok=True)
inputs = Path(__file__).resolve().parent
extension = out/('_recovery_probe'+sysconfig.get_config_var('EXT_SUFFIX'))
flags = ['c++','-std=c++17','-shared','-fPIC','-g','-O1','-fsanitize=address,undefined',
         '-fno-sanitize-recover=all','-fno-omit-frame-pointer','-Wl,--no-undefined',
         '-I'+sysconfig.get_path('include'),str(inputs/'recovery_probe.cpp'),
         '-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13','-o',str(extension)]
report = {'python':sys.version, 'command':flags, 'experiment_only':True,
          'inputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir() if p.is_file()}}
result = subprocess.run(flags,capture_output=True,text=True,timeout=120)
(out/'build.log').write_text(result.stdout+result.stderr)
report['build_exit_code'] = result.returncode
if result.returncode == 0:
    preload = ':'.join(subprocess.check_output(['c++','-print-file-name='+lib],text=True).strip()
                       for lib in ('libasan.so','libstdc++.so'))
    env = dict(os.environ, LD_PRELOAD=preload, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', PYTHONMALLOC='malloc')
    result = subprocess.run([sys.executable,'-I',str(inputs/'recovery_probe.py')],env=env,
                            capture_output=True,text=True,timeout=120)
    (out/'runtime.log').write_text(result.stdout+result.stderr)
    report['runtime_exit_code'] = result.returncode
    if (out/'native-build.json').exists():
        env.update(SPELL_HOME='/source', SPELL_DATA='/out/data')
        result = subprocess.run([sys.executable,'-I',str(inputs/'persistent_probe.py')],env=env,
                                capture_output=True,text=True,timeout=120)
        (out/'persistent-runtime.log').write_text(result.stdout+result.stderr)
        report['persistent_runtime_exit_code'] = result.returncode
        if (inputs/'chain_probe.py').exists():
            result = subprocess.run([sys.executable,'-I',str(inputs/'chain_probe.py')],env=env,
                                    capture_output=True,text=True,timeout=120)
            (out/'chain-runtime.log').write_text(result.stdout+result.stderr)
            report['chain_runtime_exit_code'] = result.returncode
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k.endswith('exit_code')}))
