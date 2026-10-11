"""Verify/export native milestone evidence. SPDX-License-Identifier: GPL-3.0-or-later."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--analysis', action='store_true', help='Require the original EXC analyzer runtime checks too')
    parser.add_argument('--goto', action='store_true', help='Also require static Step/Goto analysis and trace-jump checks')
    parser.add_argument('--storage', action='store_true', help='Require WS storage checks and all preceding native checks')
    args = parser.parse_args()
    if args.storage:
        args.goto = True
    root = Path(__file__).resolve().parent.parent
    evidence = args.evidence.resolve()
    build = json.loads((evidence/'native-build.json').read_text())
    runtime = json.loads((evidence/'util-runtime.json').read_text())
    required = ('link_exit_code','runtime_exit_code','embed_build_exit_code','embed_runtime_exit_code')
    if any(build.get(key) != 0 for key in required) or any(u['exit_code'] for u in build['units']):
        raise ValueError('Native build/link/runtime qualification failed')
    if any(runtime[key] for key in ('failures','errors','skips')) or runtime['tests'] < 16:
        raise ValueError('Native behavior qualification is incomplete')
    if build['embedding'] != {'owned_interpreter_cycles':3,'foreign_thread_finalize_rejected':True}:
        raise ValueError('Interpreter ownership qualification is incomplete')
    for name, expected in build['input_sources'].items():
        path = root/'source_port'/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Build evidence predates source: '+name)
    artifacts = {}
    for path in sorted(evidence.iterdir()):
        if path.is_file():
            artifacts[path.name] = {'bytes':path.stat().st_size,
                                   'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    report = {
        'milestone':'CPython 3.13 native UTIL compiler/frame/error ownership',
        'release':'v0.2 remains open', 'full_spell_native_qualified':False,
        'qualification_scope':'Linux x86_64, GIL-enabled CPython 3.13; original UTIL/SYN linked in a test extension and embedding executable',
        'patches':json.loads((evidence/'native-patches.json').read_text()),
        'build':build, 'runtime':runtime, 'artifacts':artifacts,
        'gaps':['DTA runtime and memory qualification','EXC Step/Goto/procedure control integration',
                'WS frame serialization/recovery','complete native/context/service setup and cleanup',
                'reproducible production native packaging','Windows native qualification'],
        'source_alpha_evidence':'source-v0.2.0a1 remains the separate historical Python/RPC wheel milestone',
    }
    if args.analysis or args.goto:
        analysis = json.loads((evidence/'analysis-runtime.json').read_text())
        if (build.get('analysis_link_exit_code') != 0 or build.get('analysis_runtime_exit_code') != 0
                or len(build.get('analysis_units', [])) < (4 if args.goto else 3)
                or any(u['exit_code'] for u in build['analysis_units'])
                or analysis['tests'] < (26 if args.goto else 15) or any(analysis[k] for k in ('failures','errors','skips'))):
            raise ValueError('Original EXC analyzer qualification failed')
        report['milestone'] = 'CPython 3.13 original EXC multiline and line-table analyzers'
        report['analysis_runtime'] = analysis
        report['qualification_scope'] += '; original SPELLastAnalyzer and SPELLlnotab linked and behavior-tested'
    if args.goto:
        report['milestone'] = 'CPython 3.13 original EXC static Step/Goto analysis and C trace jumps'
        report['qualification_scope'] += '; original SPELLgoto static literal analysis, not full native Step/Goto binding integration'
    if args.storage:
        storage = json.loads((evidence/'storage-runtime.json').read_text())
        if (build.get('storage_link_exit_code') != 0 or build.get('storage_runtime_exit_code') != 0
                or {u['unit'] for u in build.get('storage_units', [])} != {'lib/SPELL_WS/src/SPELLwsStorage.C','qualify_storage.cpp'}
                or any(u['exit_code'] for u in build['storage_units'])
                or storage['tests'] < 17 or any(storage[k] for k in ('failures','errors','skips'))):
            raise ValueError('Original WS storage qualification failed')
        report['milestone'] = 'CPython 3.13 original WS storage bounds, integrity and reference ownership'
        report['storage_runtime'] = storage
        report['qualification_scope'] += '; original SPELLwsStorage including a fresh-process load/execute check'
    name = 'STORAGE' if args.storage else 'GOTO' if args.goto else 'ANALYSIS' if args.analysis else 'UTIL'
    destination = root/('docs/NATIVE_'+name+'_QUALIFICATION.json')
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'util_tests':runtime['tests'], 'analysis_tests':report.get('analysis_runtime',{}).get('tests',0),
        'storage_tests':report.get('storage_runtime',{}).get('tests',0), 'embedding_cycles':3,
        'downstream_syntax_pass':sum(u['exit_code']==0 for u in build['downstream_syntax']),
        'downstream_syntax_fail':sum(u['exit_code']!=0 for u in build['downstream_syntax']),
        'report':str(destination)}))


if __name__ == '__main__':
    main()
