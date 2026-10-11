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
    parser.add_argument('--ws-frames', action='store_true', help='Require original WS frame/data integration and shared continuation probes')
    parser.add_argument('--warm', action='store_true', help='Require original WS controller and manager logical recovery')
    parser.add_argument('--dta-checkpoints', action='store_true', help='Require native DTA graphs through serialization and original WS recovery')
    parser.add_argument('--executor-command', action='store_true', help='Require the original standalone executor, native bindings and command behavior')
    parser.add_argument('--executor-warm', action='store_true', help='Require actual executor crash recovery with native runtime data')
    parser.add_argument('--context', action='store_true', help='Require original listener/context IPC lifecycle and process/socket regressions')
    parser.add_argument('--service-bindings', action='store_true', help='Require native service registration and owned worker lifecycle')
    parser.add_argument('--service', action='store_true', help='Require actual context-launched service and controlled shutdown')
    args = parser.parse_args()
    if args.service:
        args.service_bindings=True
    if args.service_bindings:
        args.context = True
    if args.context:
        args.executor_warm = True
    if args.executor_warm:
        args.executor_command = True
    if args.executor_command:
        args.dta_checkpoints = True
    if args.dta_checkpoints:
        args.warm = True
    if args.warm:
        args.ws_frames = True
    if args.ws_frames:
        args.cold = True
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
    for path in sorted(evidence.rglob("*")):
        if path.is_file():
            artifacts[path.relative_to(evidence).as_posix()] = {'bytes':path.stat().st_size,
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
    if args.ws_frames:
        ws = json.loads((evidence/'ws-runtime.json').read_text())
        probe = json.loads((evidence/'build.json').read_text())
        required = {'lib/SPELL_WS/src/'+name for name in ('SPELLwsFrame.C','SPELLwsStaticData.C','SPELLwsDynamicData.C')}
        if (build.get('ws_runtime_exit_code') != 0 or ws['tests'] < 12
                or any(ws[k] for k in ('failures','errors','skips'))
                or not required.issubset({u['unit'] for u in build['analysis_units']})
                or report['library_syntax']['pass'] < 142):
            raise ValueError('Original WS frame/data qualification failed')
        for name,digest in probe['inputs'].items():
            if hashlib.sha256((root/'source_port/experiments'/name).read_bytes()).hexdigest() != digest:
                raise ValueError('Evidence predates continuation probe: '+name)
        for name,digest in probe['shared_continuation'].items():
            if hashlib.sha256((root/'source_port/native'/name).read_bytes()).hexdigest() != digest:
                raise ValueError('Evidence predates shared continuation: '+name)
        for key in ('build_exit_code','runtime_exit_code','persistent_runtime_exit_code','chain_runtime_exit_code'):
            if probe.get(key) != 0: raise ValueError('Shared continuation probe failed: '+key)
        report['continuation_probes'] = {'build':probe}
        for name,minimum in (('recovery',14),('persistent',13),('chain',11)):
            result = json.loads((evidence/(name+'-probe.json')).read_text())
            if result['tests'] < minimum or any(result[k] for k in ('failures','errors','skips')):
                raise ValueError('Shared continuation qualification failed: '+name)
            report['continuation_probes'][name] = result
        report['ws_runtime'] = ws
        report['milestone'] = 'CPython 3.13 original WS frame/static/dynamic state integration'
        report['qualification_scope'] += '; original WS frame/data classes use the shared exact-build continuation engine, inspection views, atomic single-frame storage and restored trace dispatch'
    if args.warm:
        warm = json.loads((evidence/'warm-runtime.json').read_text())
        if (build.get('warm_runtime_exit_code') != 0 or warm['tests'] < 14
                or any(warm[k] for k in ('failures','errors','skips'))
                or report['ws_runtime']['tests'] < 13
                or report['library_syntax'] != {'total':143,'pass':143,'fail':0}
                or 'lib/SPELL_WS/src/SPELLwsWarmStartImpl.C' not in {u['unit'] for u in build['analysis_units']}):
            raise ValueError('Original WS controller/manager qualification failed')
        report['warm_runtime'] = warm
        report['milestone'] = 'CPython 3.13 original WS controller and frame-manager logical continuation'
        report['qualification_scope'] += '; one atomic caller graph, original WS callbacks and manager models, 14 integrated checks including SIGKILL/fresh-process recovery and repeated checkpoints'
        report['gaps'][2] = 'Native DTA graph serialization, external dependency/resource recovery and actual executor/CIF checkpoint dispatch'
    if args.dta_checkpoints:
        checkpoint = json.loads((evidence/'dta-checkpoint-runtime.json').read_text())
        integrated = json.loads((evidence/'dta-warm-runtime.json').read_text())
        if (build.get('dta_checkpoint_runtime_exit_code') != 0 or checkpoint['tests'] < 12 or checkpoint['failures']
                or any(row['exit_code'] for row in checkpoint['cases'])
                or build.get('dta_warm_runtime_exit_code') != 0 or integrated['tests'] < 3
                or any(integrated[k] for k in ('failures','errors','skips'))):
            raise ValueError('Native DTA checkpoint qualification failed')
        report['dta_checkpoint_runtime'] = checkpoint
        report['dta_warm_runtime'] = integrated
        report['milestone'] = 'CPython 3.13 native DTA graph serialization and original WS recovery'
        report['qualification_scope'] += '; 12 isolated DTA serialization cases and 3 SIGKILL/fresh-process procedure recoveries with native data, aliases, constraints and subclass state'
        report['gaps'][2] = 'External dependency/resource recovery and actual executor/CIF checkpoint dispatch'
    if args.executor_command:
        command = json.loads((evidence/'executor-build.json').read_text())
        behavior = json.loads((evidence/'executor-runtime.json').read_text())
        required = ('library_link_exit_code','qualification_exit_code','bindings_build_exit_code',
            'bindings_runtime_exit_code','bindings_framework_exit_code')
        if (any(command.get(key) != 0 for key in required) or command['command']['link_exit_code'] != 0
                or len(command['libraries']) != 13 or any(row['exit_code'] for row in command['units'])
                or behavior['tests'] < 17 or any(behavior[key] for key in ('failures','errors','skips'))):
            raise ValueError('Original executor command qualification failed')
        expected_units = {name for library in command['libraries'] for name in build['library_manifest'][library]['units']}
        if expected_units != {row['unit'] for row in command['units']}:
            raise ValueError('Executor does not link its original library manifest')
        if command['native_build_sha256'] != hashlib.sha256((evidence/'native-build.json').read_bytes()).hexdigest():
            raise ValueError('Executor evidence differs from component evidence')
        for name,digest in command['input_sources'].items():
            if hashlib.sha256((root/'source_port'/name).read_bytes()).hexdigest() != digest:
                raise ValueError('Executor evidence predates recipe: '+name)
        for name,digest in (('SPELL-ExecutorCmd_v3',command['command']['sha256']),
                ('libspell_executor313.so',command['runtime_sha256'])):
            if hashlib.sha256((evidence/name).read_bytes()).hexdigest() != digest:
                raise ValueError('Executor binary differs: '+name)
        cycles={}
        for name,expected in (('embed',{'cycles':3,'binding_type_lifetimes':2400,'builtins_unchanged':True}),
                ('framework',{'cycles':1,'binding_type_lifetimes':800,'builtins_unchanged':True})):
            lines=[line for line in (evidence/('bindings-'+name+'-runtime.log')).read_text().splitlines() if line.startswith('{')]
            if len(lines)!=1 or json.loads(lines[0])!=expected:
                raise ValueError('Binding lifecycle qualification failed: '+name)
            cycles[name]=expected
        report['executor_build']=command
        report['executor_runtime']=behavior
        report['binding_lifecycle']=cycles
        report['example_driver_patches']=json.loads((evidence/'executor-example-driver-patches.json').read_text())
        report['milestone']='Original standalone executor and native bindings with explicit SPELL namespace'
        report['qualification_scope'] += '; original ExecutorCmd, automatic CIF, real dispatcher and original example driver (eight import corrections); command behavior including invalid prompt rejection; native binding cycles and one full-framework interpreter lifetime'
        report['gaps']=['Actual executor warm-start checkpoints/recovery and service/context lifecycle',
            'Complete executor/CIF shared-data, child-procedure, scheduler and controller command behavior',
            'Operational driver/DSS integration and external effect/resource recovery',
            'Production distribution and supported platform/host matrix',
            'Full RPC framework reinitialization within one process is unsupported; use a fresh process']
    if args.executor_warm:
        required={'test_warm_line_recovers_native_nested_stack','test_warm_step_recovers_native_nested_stack',
            'test_missing_startup_files_fail_without_native_abort','test_warm_missing_recovery_files_fail_cleanly',
            'test_warm_rejects_changed_source_and_preserves_checkpoint','test_warm_rejects_corrupt_payload_and_preserves_checkpoint'}
        if (report['executor_runtime']['tests'] < 23 or not required.issubset(report['executor_runtime']['cases'])
                or report['dta_checkpoint_runtime']['tests'] < 13):
            raise ValueError('Actual executor warm recovery qualification incomplete')
        report['milestone']='Original executor SIGKILL recovery with logical callers and native runtime data'
        report['qualification_scope'] += '; actual ON_LINE and ON_STEP checkpoints, fresh-process recovery, nested return operands, native data and ARGS/IVARS/PROC aliases; safe Python cleanup, missing files and corrupt/source-mismatched checkpoint rejection without deleting input checkpoints'
        report['gaps'][0]='Native service/context lifecycle, complete executor/CIF control and broader recovery scenarios'
        report['warm_checkpoint_format']='SPELL-continuation/2; runtime-owned data shares the procedure graph'
        report['step_checkpoint_boundary']='First safe line after the native Step binding returns'
    if args.context:
        context = json.loads((evidence/'context-build.json').read_text())
        behavior = json.loads((evidence/'context-runtime.json').read_text())
        required = ('process_build_exit_code','process_runtime_exit_code','peer_build_exit_code','server_peer_build_exit_code','qualification_exit_code')
        if any(context.get(key)!=0 for key in required):
            raise ValueError('Context/process qualification failed')
        if behavior['tests']<2 or any(behavior[key] for key in ('failures','errors','skips')):
            raise ValueError('Context IPC lifecycle qualification incomplete')
        if set(context['programs']) != {'SPELL_Context','SPELL_Listener','SPELL_Executor_v3','SPELL_Service_v3'}:
            raise ValueError('Original server programs missing')
        for entry in context['programs'].values():
            if entry.get('link_exit_code')!=0 or any(row['exit_code'] for row in entry['units']):
                raise ValueError('Server program compilation failed')
            if hashlib.sha256((evidence/entry['executable']).read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('Server executable differs: '+entry['executable'])
        for name,digest in context['input_sources'].items():
            if hashlib.sha256((root/'source_port'/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Context evidence predates recipe: '+name)
        if context['executor_build_sha256']!=hashlib.sha256((evidence/'executor-build.json').read_bytes()).hexdigest():
            raise ValueError('Context executor dependency evidence differs')
        lines=[line for line in (evidence/'process-runtime.log').read_text().splitlines() if line.startswith('{')]
        expected={'socket_reuse_cases':4,'exit_status_cases':2,'callback_restarts':20,'duplicate_rejected':True,'child_signal_mask_checks':4,'interrupted_waits':1,'incoming_completion_cases':4}
        if len(lines)!=1 or json.loads(lines[0])!=expected:
            raise ValueError('Process/socket lifecycle evidence incomplete')
        report['context_build']=context
        report['context_runtime']=behavior
        report['process_runtime']=expected
        report['milestone']='Original listener/context/server executor IPC startup, Run and orderly shutdown'
        report['qualification_scope'] += '; listener launches the original context, queries its status and closes it through original IPC; 20 callback-driven process restarts with concurrent waits, fast child exit codes, duplicate rejection and four reused descriptor cleanup cases; context-launched original server executor, explicit imports/native arguments, visible Run, CIF notifications, file result and successful child exit without force-kill fallback'
        report['gaps'][0]='Actual native service lifecycle and complete server controller/CIF behavior'
    if args.service_bindings:
        if behavior.get('lifecycle_runs',0)<6:
            raise ValueError('Repeated listener/context lifecycle evidence incomplete')
        if any(context.get(key)!=0 for key in ('service_bindings_build_exit_code','service_bindings_runtime_exit_code')):
            raise ValueError('Native service binding qualification failed')
        log=(evidence/'service-bindings-runtime.log').read_text()
        for marker in ('SERVICE_BINDING_TESTS 9','SERVICE_WORKERS_JOINED','SERVICE_BINDINGS_COMPLETE callbacks='):
            if marker not in log: raise ValueError('Service binding evidence incomplete: '+marker)
        if any(marker in log for marker in ('ERROR: AddressSanitizer','runtime error:','Fatal Python error')):
            raise ValueError('Service sanitizer failure')
        report['service_bindings']={'tests':9,'workers_joined':True,'builtins_unchanged':True,
            'native_registration':True,'native_watchdog':True,'full_service_process_qualified':False}
        report['milestone']='Original native service registration, watchdog binding and owned worker shutdown'
        report['qualification_scope'] += '; nine native service registration/worker/watchdog checks, all owned threads joined before interpreter finalization'
    if args.service:
        if behavior.get('lifecycle_runs')!=7 or behavior.get('service_runs')!=1 or behavior['tests']<3:
            raise ValueError('Actual service process evidence incomplete')
        log=(evidence/'service-0-peer.log').read_text()
        for marker in ('SERVICE_EXECUTABLE_VERIFIED','NATIVE_SERVICE_RUNNING','CONTEXT_CLOSED'):
            if marker not in log: raise ValueError('Service IPC evidence missing: '+marker)
        if (evidence/'service-result.txt').read_text()!='42':
            raise ValueError('Native service worker/data result differs')
        pid=(evidence/'service-pid.txt').read_text()
        if not pid.isdecimal() or (evidence/'service-closed.txt').read_text()!=pid:
            raise ValueError('Service Python finally did not run in the original child')
        report['service_runtime']={'tests':1,'original_context_watchdog_launch':True,
            'actual_service_executable_verified':True,'explicit_runtime_imports':True,
            'native_data_and_worker_result':42,'ipc_close':True,'python_finally':True,
            'child_reaped':True,'full_service_qualified':False}
        report['milestone']='Original service launch, native runtime data and controlled shutdown'
        report['qualification_scope'] += '; original context watchdog launches SPELL-Service_v3, live /proc executable identity, native ARGS/IVARS/PROC and worker result, original Close terminates the service and runs Python finally, owned workers are joined and the child exits normally'
        report['gaps'][0]='Broader server controller/CIF behavior, service recovery/restart/failure scenarios and complete native memory audit'
    name = 'SERVICE' if args.service else 'SERVICE_BINDINGS' if args.service_bindings else 'CONTEXT' if args.context else 'EXECUTOR_WARM' if args.executor_warm else 'EXECUTOR_COMMAND' if args.executor_command else 'DTA_CHECKPOINT' if args.dta_checkpoints else 'WARM' if args.warm else 'WS_FRAMES' if args.ws_frames else 'COLD' if args.cold else 'DTA' if args.dta else 'MANAGER' if args.manager else 'FACTORY' if args.factory else 'FRAMES' if args.frames else 'BYTECODE' if args.bytecode else 'WATCH' if args.watch else 'STORAGE' if args.storage else 'GOTO' if args.goto else 'ANALYSIS' if args.analysis else 'UTIL'
    destination = root/('docs/NATIVE_'+name+'_QUALIFICATION.json')
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'util_tests':runtime['tests'], 'analysis_tests':report.get('analysis_runtime',{}).get('tests',0),
        'storage_tests':report.get('storage_runtime',{}).get('tests',0), 'embedding_cycles':3,
        'manager_tests':report.get('manager_runtime',{}).get('tests',0),
        'dta_tests':report.get('dta_runtime',{}).get('tests',0),
        'cold_tests':report.get('cold_runtime',{}).get('tests',0),
        'ws_frame_tests':report.get('ws_runtime',{}).get('tests',0),
        'warm_tests':report.get('warm_runtime',{}).get('tests',0),
        'dta_checkpoint_tests':report.get('dta_checkpoint_runtime',{}).get('tests',0),
        'dta_warm_tests':report.get('dta_warm_runtime',{}).get('tests',0),
        'executor_command_tests':report.get('executor_runtime',{}).get('tests',0),
        'downstream_syntax_pass':sum(u['exit_code']==0 for u in build['downstream_syntax']),
        'downstream_syntax_fail':sum(u['exit_code']!=0 for u in build['downstream_syntax']),
        'report':str(destination)}))


if __name__ == '__main__':
    main()
