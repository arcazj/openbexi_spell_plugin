"""Validate persistent recovery experiment and original WS build evidence.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', required=True, type=Path)
parser.add_argument('--chain', action='store_true', help='Require logical caller-continuation qualification')
args = parser.parse_args()
directory = args.evidence.resolve()
root = Path(__file__).resolve().parents[2]
build = json.loads((directory/'build.json').read_text())
native = json.loads((directory/'native-build.json').read_text())
runtime = json.loads((directory/'persistent-probe.json').read_text())
memory = json.loads((directory/'recovery-probe.json').read_text())
if any(build.get(k) != 0 for k in ('build_exit_code','runtime_exit_code','persistent_runtime_exit_code')):
    raise ValueError('Recovery experiment failed')
reports = {'persistent':(runtime,13), 'memory':(memory,8)}
if args.chain:
    if build.get('chain_runtime_exit_code') != 0:
        raise ValueError('Caller recovery experiment failed')
    reports['memory'] = (memory,10)
    reports['callers'] = (json.loads((directory/'chain-probe.json').read_text()),11)
for name, minimum in (('util',18),('analysis',57),('storage',17)):
    reports[name] = (json.loads((directory/(name+'-runtime.json')).read_text()),minimum)
for name, (report, minimum) in reports.items():
    if report['tests'] < minimum or any(report[k] for k in ('failures','errors','skips')):
        raise ValueError(name+' runtime qualification failed')
for key in ('link_exit_code','runtime_exit_code','embed_build_exit_code','embed_runtime_exit_code',
            'analysis_link_exit_code','analysis_runtime_exit_code','storage_link_exit_code','storage_runtime_exit_code'):
    if native.get(key) != 0:
        raise ValueError('Original native qualification failed: '+key)
for group in ('units','analysis_units','storage_units'):
    if any(unit['exit_code'] for unit in native[group]):
        raise ValueError('Native compilation failed: '+group)
for name, digest in native['input_sources'].items():
    if hashlib.sha256((root/'source_port'/name).read_bytes()).hexdigest() != digest:
        raise ValueError('Evidence predates native input: '+name)
for name, digest in build['inputs'].items():
    if hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() != digest:
        raise ValueError('Evidence predates experiment input: '+name)
artifact_names = ['build.json','persistent-runtime.log','persistent-probe.json','runtime.log',
                  'recovery-probe.json','native-build.json','native-patches.json']
artifact_names += [p.name for p in directory.glob('_recovery_probe*.so')]
if args.chain:
    artifact_names += ['chain-runtime.log','chain-probe.json']
report = {'status':'single-frame persistence experiment; v0.2 remains open',
    'full_spell_warm_start_qualified':False, 'build':build,
    'native_build_input_hashes':native['input_sources'],
    'runtime':{name:entry[0] for name,entry in reports.items()},
    'artifacts':{name:{'bytes':(directory/name).stat().st_size,
        'sha256':hashlib.sha256((directory/name).read_bytes()).hexdigest()} for name in artifact_names},
    'unqualified':['nested caller continuation','arguments/closures/generators/coroutines',
        'arbitrary custom objects and resource reconnection','original executor and WS lifecycle integration',
        'DSS exactly-once effects','Windows','other CPython builds','historical tracebacks'],
    'serialization':'application-owned short-lived checkpoints; exact interpreter/source/backend/codec identity; cloudpickle 3.1.2 hash-pinned'}
if args.chain:
    report['status'] = 'logical caller persistence experiment; v0.2 remains open'
    report['unqualified'] = ['physical caller-frame chain reconstruction', 'C-call boundaries',
        'generators/coroutines', 'arbitrary custom objects and external resource reconnection',
        'original executor and WS lifecycle integration', 'DSS exactly-once effects',
        'external module dependency identity', 'Windows', 'other CPython builds', 'historical tracebacks']
destination = root/('docs/CALLER_RECOVERY_PROBE.json' if args.chain else 'docs/PERSISTENT_RECOVERY_PROBE.json')
destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'persistent_tests':runtime['tests'],'memory_tests':memory['tests'],
    'status':report['status'], 'report':str(destination)}))
