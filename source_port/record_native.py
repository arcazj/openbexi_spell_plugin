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
    parser.add_argument('--watch', action='store_true', help='Require live variable-monitor checks and all preceding checks')
    parser.add_argument('--bytecode', action='store_true', help='Require source-bound bytecode checks and all preceding checks')
    parser.add_argument('--frames', action='store_true', help='Require public frame accessor checks and original v3 library inventory')
    parser.add_argument('--factory', action='store_true', help='Require original frame-factory ownership and WS header isolation checks')
    parser.add_argument('--manager', action='store_true', help='Require linked original frame-manager component behavior and filter lifecycle')
    parser.add_argument('--dta', action='store_true', help='Require original DTA types, value conversion and interpreter lifecycle checks')
    parser.add_argument('--cold', action='store_true', help='Require original manager cold evaluation and all preceding component checks')
    args = parser.parse_args()
    if args.cold:
        args.dta = True
    if args.dta:
        args.manager = True
    if args.manager:
        args.factory = True
    if args.factory:
        args.frames = True
    if args.frames:
        args.bytecode = True
    if args.bytecode:
        args.watch = True
    if args.watch:
        args.storage = True
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
    if args.watch:
        if (report['analysis_runtime']['tests'] < 43
                or 'lib/SPELL_EXC/src/SPELLvariableMonitor.C' not in {u['unit'] for u in build['analysis_units']}):
            raise ValueError('Original variable monitor qualification failed')
        report['milestone'] = 'CPython 3.13 original live variable monitor and previous native milestones'
        report['qualification_scope'] += '; original SPELLvariableMonitor live locals/cells, edits and notifications'
    if args.bytecode:
        if (report['analysis_runtime']['tests'] < 57
                or 'lib/SPELL_EXC/src/SPELLbytecode.C' not in {u['unit'] for u in build['analysis_units']}):
            raise ValueError('Original bytecode analyzer qualification failed')
        report['milestone'] = 'CPython 3.13 original bytecode analyzer with identity-bound source metadata'
        report['qualification_scope'] += '; original SPELLbytecode public disassembly and source-scope analysis'
    if args.frames:
        manifest = build.get('library_manifest', {})
        all_units = {u for lib in manifest.values() for u in lib['units']}
        checked = {u['unit']:u['exit_code'] for u in build['downstream_syntax'] + build.get('remaining_library_syntax', [])}
        checked.update({u['unit']:u['exit_code'] for u in build['units'] if u['unit'].startswith('lib/')})
        frames = {'lib/SPELL_EXC/src/'+name for name in ('SPELLexecutionModel.C','SPELLexecutorImpl.C','SPELLserviceImpl.C')}
        if (runtime['tests'] < 18 or len(manifest) != 16 or len(all_units) != 143
                or set(checked) != all_units or any(checked.get(u) != 0 for u in frames)
                or any(u['exit_code'] for u in build['remaining_library_syntax'])):
            raise ValueError('Public frame accessor/library inventory qualification failed')
        report['milestone'] = 'CPython 3.13 public executor frame access and original Python 3 library inventory'
        report['qualification_scope'] += '; public frame getters tested, executor/model/service units syntax-checked; all 143 original v3 library units inventoried'
        report['library_syntax'] = {'total':len(checked), 'pass':sum(v==0 for v in checked.values()),
            'fail':sum(v!=0 for v in checked.values())}
    if args.factory:
        required = {'lib/SPELL_EXC/src/SPELLinterpreter.C','lib/SPELL_EXC/src/SPELLserviceInterpreter.C',
                    'lib/SPELL_WS/src/SPELLwsDictDataHandler.C'}
        checked = {u['unit']:u['exit_code'] for u in build['downstream_syntax']}
        if runtime['tests'] < 21 or any(checked.get(name) != 0 for name in required):
            raise ValueError('Frame factory/header isolation qualification failed')
        report['milestone'] = 'CPython 3.13 original frame-factory ownership and warm-start header isolation'
        report['qualification_scope'] += '; original procedure/function frame creation and release, current __file__ on load'
    if args.manager:
        manager = json.loads((evidence/'manager-runtime.json').read_text())
        required = {'lib/SPELL_EXC/src/'+name for name in ('SPELLframeManager.C','SPELLexecutionModel.C','SPELLexecutor.C')}
        if (build.get('manager_runtime_exit_code') != 0 or manager['tests'] < 12
                or any(manager[k] for k in ('failures','errors','skips'))
                or not required.issubset({u['unit'] for u in build['analysis_units']})
                or 'ws_filter.cpp' not in {u['unit'] for u in build['units']}):
            raise ValueError('Original frame manager qualification failed')
        report['manager_runtime'] = manager
        report['milestone'] = 'CPython 3.13 original frame-manager live edits, ownership and interpreter-local WS filter'
        report['qualification_scope'] += '; original manager public methods with watch/resource notifications disabled; actual CIF/CFG/PRD dependencies linked; filter tested across interpreter cycles'
    if args.dta:
        dta = json.loads((evidence/'dta-runtime.json').read_text())
        required = ('dta_link_exit_code','dta_runtime_exit_code','dta_embed_build_exit_code','dta_embed_runtime_exit_code')
        if (any(build.get(key) != 0 for key in required) or dta['tests'] < 18 or dta['failures']
                or any(row['exit_code'] for row in dta['cases'])
                or {u['unit'] for u in build['dta_units'] if u['unit'].startswith('lib/')} != set(build['library_manifest']['SPELL_DTA']['units'])
                or any(u['exit_code'] for u in build['dta_units'])
                or build.get('dta_embedding') != {'owned_interpreter_cycles':3,'container_lifetimes':3000}):
            raise ValueError('Original DTA runtime/lifecycle qualification failed')
        report['dta_runtime'] = dta
        report['milestone'] = 'CPython 3.13 original DTA native type ownership, conversion and interpreter lifecycle'
        report['qualification_scope'] += '; all five original DTA units linked, 18 isolated-process cases, 3000 container lifetimes over three additional interpreter cycles'
        report['gaps'][0] = 'DTA notifications and interactive prompts through the real executor/CIF'
    if args.cold:
        cold = json.loads((evidence/'cold-runtime.json').read_text())
        if (build.get('cold_runtime_exit_code') != 0 or cold['tests'] < 8
                or any(cold[k] for k in ('failures','errors','skips'))):
            raise ValueError('Original manager cold execution qualification failed')
        report['cold_runtime'] = cold
        report['milestone'] = 'CPython 3.13 original manager cold evaluation with live frames'
        report['qualification_scope'] += '; qualification trace dispatcher calls original manager callbacks; nested calls, live edits, error/control propagation and repeated reloads'
    name = 'COLD' if args.cold else 'DTA' if args.dta else 'MANAGER' if args.manager else 'FACTORY' if args.factory else 'FRAMES' if args.frames else 'BYTECODE' if args.bytecode else 'WATCH' if args.watch else 'STORAGE' if args.storage else 'GOTO' if args.goto else 'ANALYSIS' if args.analysis else 'UTIL'
    destination = root/('docs/NATIVE_'+name+'_QUALIFICATION.json')
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'util_tests':runtime['tests'], 'analysis_tests':report.get('analysis_runtime',{}).get('tests',0),
        'storage_tests':report.get('storage_runtime',{}).get('tests',0), 'embedding_cycles':3,
        'manager_tests':report.get('manager_runtime',{}).get('tests',0),
        'dta_tests':report.get('dta_runtime',{}).get('tests',0),
        'cold_tests':report.get('cold_runtime',{}).get('tests',0),
        'downstream_syntax_pass':sum(u['exit_code']==0 for u in build['downstream_syntax']),
        'downstream_syntax_fail':sum(u['exit_code']!=0 for u in build['downstream_syntax']),
        'report':str(destination)}))


if __name__ == '__main__':
    main()
