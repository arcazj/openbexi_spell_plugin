"""Bind feasibility results to experiment inputs. SPDX-License-Identifier: GPL-3.0-or-later."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', required=True, type=Path)
args = parser.parse_args()
directory = args.evidence.resolve()
build = json.loads((directory/'build.json').read_text())
runtime = json.loads((directory/'recovery-probe.json').read_text())
if build.get('build_exit_code') != 0 or build.get('runtime_exit_code') != 0:
    raise ValueError('Recovery feasibility experiment failed')
if runtime['tests'] < 6 or any(runtime[k] for k in ('failures','errors','skips')):
    raise ValueError('Recovery feasibility coverage incomplete')
for name, digest in build['inputs'].items():
    if hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() != digest:
        raise ValueError('Evidence predates experiment input: '+name)
report = {'status':'research only; v0.2 remains open', 'build':build, 'runtime':runtime,
          'artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                       for p in directory.iterdir() if p.is_file()},
          'unqualified':['persistent serialization','crash/process recovery','nested caller frames',
                         'arguments/closures/generators/coroutines','object graph and external resources',
                         'original SPELL WS integration','Windows','other CPython builds']}
destination = Path(__file__).resolve().parents[2]/'docs/RECOVERY_PROBE.json'
destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'tests':runtime['tests'], 'status':report['status'], 'report':str(destination)}))
