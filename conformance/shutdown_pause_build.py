"""Retain original-native controls before and after one checked source change."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sysconfig
import zipfile

from incremental_native import rebuild
import shutdown_pause_patches as patch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


output = Path('/shutdown-pause')
output.mkdir()
source = Path('/source') / patch.SOURCE
archive = Path('/input/SPELL2.6.10-src.zip')
assert sha(archive) == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
native = json.loads(Path('/out/native-build.json').read_bytes())
context = json.loads(Path('/out/context-build.json').read_bytes())
units = [row for row in context['programs']['SPELL_Context']['units'] if row['unit'].startswith('lib/')]
assert next(row for row in units if row['unit'] == patch.SOURCE)['sha256'] == sha(source) == patch.PORTED
with zipfile.ZipFile(archive) as bundle:
    original = bundle.read(patch.SOURCE)
ported = source.read_bytes()
patched = patch.apply(patch.SOURCE, original, ported)
for label, raw in [('original', original), ('ported', ported), ('patched', patched)]:
    target = output / label / patch.SOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
for name in ('shutdown_pause_build.py', 'shutdown_pause_patches.py', 'shutdown_pause.cpp', 'incremental_native.py'):
    shutil.copyfile(Path(__file__).parent / name, output / name)

environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
common = ['-L' + sysconfig.get_config_var('LIBDIR'), '-lpython3.13', '-llog4cplus',
          '-lxerces-c', '-lz', '-lmenu', '-lncurses']
report = {'accepted': False, 'profile': 'original-context-executor-model',
          'limitation': 'Virtual command dispatch is synchronized by the probe. Each scenario retains its uninitialized IPC model for its entire private process; actual IPC lifecycle/teardown qualification is separate.',
          'source': {label + '_sha256': hashlib.sha256(raw).hexdigest()
                     for label, raw in [('original', original), ('ported', ported), ('patched', patched)]},
          'inputs': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
          'base_builds': {name: sha(Path('/out') / name) for name in ('native-build.json', 'context-build.json')},
          'full_v05_accepted': False, 'full_v06_accepted': False}


def probe(name, replacement=None):
    binary = output / (name + '-probe')
    objects = [str(replacement if replacement and row['unit'] == patch.SOURCE else Path('/out') / row['object']) for row in units]
    command = [*native['flags'], str(output / 'shutdown_pause.cpp'), *objects, *common, '-o', str(binary)]
    compiled = subprocess.run(command, capture_output=True, timeout=90)
    log = output / (name + '-build.log')
    log.write_bytes(compiled.stdout + compiled.stderr)
    entry = {'command': command, 'compile_exit_code': compiled.returncode, 'compile_log_sha256': sha(log)}
    report[name] = entry
    if compiled.returncode:
        print((compiled.stdout + compiled.stderr).decode(errors='replace'), flush=True)
    assert compiled.returncode == 0, name
    entry.update(binary_sha256=sha(binary), scenarios={}, cases=[])
    tests = failures = 0
    for scenario in ('already-closing', 'already-finished', 'pause-reached', 'interrupt-reached',
                     'close-during-pause', 'close-during-interrupt', 'finish-during-pause',
                     'finish-during-interrupt', 'real-timeout-with-noise', 'ordinary-wait-unchanged'):
        result = subprocess.run([str(binary), scenario], capture_output=True, timeout=12, env=environment)
        log = output / (name + '-' + scenario + '.log')
        log.write_bytes(result.stdout + result.stderr)
        matches = re.findall(rb'^\{"tests":\d+,"failures":\d+\}$', result.stdout, re.M)
        if len(matches) != 1:
            print((result.stdout + result.stderr).decode(errors='replace'), flush=True)
        assert len(matches) == 1, (name, scenario)
        summary = json.loads(matches[0])
        assert summary['tests'] == 1 and result.returncode == bool(summary['failures'])
        assert b'AddressSanitizer:' not in log.read_bytes() and b'runtime error:' not in log.read_bytes()
        tests += summary['tests']; failures += summary['failures']
        entry['scenarios'][scenario] = dict(exit_code=result.returncode, result=summary, log_sha256=sha(log))
        entry['cases'].extend(re.findall(r'^CASE ([^\n]+)$', result.stdout.decode(), re.M))
    entry.update(exit_code=int(failures != 0), result=dict(tests=tests, failures=failures))
    return entry


try:
    baseline = probe('baseline')
    assert baseline['exit_code'] == 1 and baseline['result'] == {'tests': 10, 'failures': 5}, baseline
    source.write_bytes(patched)
    compiled = rebuild([patch.SOURCE], output / 'compiled')
    replacement = output / 'compiled' / compiled['units'][patch.SOURCE]['object']
    candidate = probe('candidate', replacement)
    assert candidate['exit_code'] == 0 and candidate['result'] == {'tests': 10, 'failures': 0}, candidate
    report.update(passed=True, artifact={name: row['sha256'] for name, row in compiled['artifacts'].items()},
                  prior_artifact={name: row['original_sha256'] for name, row in compiled['artifacts'].items()},
                  incremental_build_sha256=sha(output / 'compiled/incremental-build.json'))
finally:
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
