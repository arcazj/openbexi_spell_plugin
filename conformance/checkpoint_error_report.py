"""Bind the narrow exception-unwind correction to retained actual native evidence."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from checkpoint_error_provenance import qualification_identity


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load(identifier,kind='checkpoint-error'):
    path=Path(identifier)
    if not path.is_file():path=ROOT/'.qualification/v0.6'/kind/identifier/'result.json'
    return json.loads(path.read_bytes()),dict(path=str(path),sha256=sha(path))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','audit','candidate','expanded','ipc-baseline','ipc-candidate','ipc-blocker'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--gate')
    parser.add_argument('--integrated-gate-dir',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    reports={};references={}
    for key in ('baseline','audit','candidate','expanded','ipc_baseline','ipc_candidate','ipc_blocker'):
        reports[key],references[key]=load(getattr(args,key),'checkpoint-error-gate' if key=='gate' else 'checkpoint-error')
    ordinary={'direct-valueerror','lambda-valueerror','named-valueerror','lambda-keyerror','lambda-success','lambda-original-driver'}
    expanded={'nested-unwind','finally-unwind','replace-error','recursive-unwind','repeated-catch'}
    ipc={'module-error','named-error','nested-error','user-action-error'}
    for key,cases,modes,executions in (
            ('baseline',ordinary,{'ON_LINE','ON_STEP'},{'fresh','resume'}),
            ('candidate',ordinary,{'ON_LINE','ON_STEP'},{'fresh','resume'}),
            ('expanded',expanded,{'ON_LINE','ON_STEP'},{'fresh','resume'}),
            ('ipc_baseline',ipc,{'DISABLED'},None),('ipc_candidate',ipc,{'DISABLED'},None)):
        data=reports[key]
        assert data['controller_exit_code']==0,key
        assert set(data['options']['cases'])==cases,key
        assert set(data['options']['modes'])==modes,key
        if executions is not None:
            assert set(data['options']['executions'])==executions,key
            expected={mode+':'+case+':'+execution for mode in modes for case in cases for execution in executions}
        else:
            expected={mode+':'+case for mode in modes for case in cases}
        assert set(data['checks'])==expected,key
        if key in ('candidate','expanded','ipc_candidate'):
            controller='conformance/checkpoint_error_'+('controller.py' if executions else 'ipc.py')
            assert data['inputs'][controller]==sha(ROOT/controller),key
        for identifier,row in data['checks'].items():
            assert row['case'] in cases and row['mode'] in modes,identifier
            assert identifier==row['mode']+':'+row['case']+(':'+row['execution'] if executions else ''),identifier
    base,candidate=reports['baseline'],reports['candidate']
    assert len(base['checks'])==len(candidate['checks'])==24
    assert set(base['checks'])==set(candidate['checks'])
    corrected=[]
    for key,row in candidate['checks'].items():
        assert row['passed'] and row['returncode']==0,key
        assert row['procedure_sha256']==base['checks'][key]['procedure_sha256'],key
        if not base['checks'][key]['passed']:
            assert 'checkpoint requires a synchronous thread-owned frame' in base['checks'][key]['log']
            corrected.append(key)
    assert len(corrected)==16
    assert len(reports['expanded']['checks'])==20
    assert all(c['passed'] for c in reports['expanded']['checks'].values())
    for name in ('ipc_baseline','ipc_candidate'):
        assert len(reports[name]['checks'])==4
        assert all(c['passed'] for c in reports[name]['checks'].values())
    assert set(reports['ipc_baseline']['checks'])==set(reports['ipc_candidate']['checks'])
    for key,row in reports['ipc_baseline']['checks'].items():
        assert row['procedure_sha256']==reports['ipc_candidate']['checks'][key]['procedure_sha256']
    identity=qualification_identity(candidate['runtime_sources'],candidate['inputs'],candidate.get('lf_normalized_inputs'))
    for name in ('expanded','ipc_candidate'):
        assert reports[name]['runtime_image']==candidate['runtime_image']
        assert qualification_identity(reports[name]['runtime_sources'],reports[name]['inputs'],
            reports[name].get('lf_normalized_inputs'))==identity
    assert bool(args.gate)!=bool(args.integrated_gate_dir), 'Select exactly one real gate format'
    if args.gate:
        gate,references['gate']=load(args.gate,'checkpoint-error-gate')
        assert gate['controller_exit_code']==gate['exit_code']==0
        assert gate['qualifier_sha256']==sha(ROOT/'source_port/qualify_executor.py')
        assert gate['runtime_sha256']==identity['runtime_sha256']
        gate_result=gate['gate']
    else:
        gate_path=args.integrated_gate_dir/'executor-runtime.json'
        build_path=args.integrated_gate_dir/'executor-build.json'
        gate_result=json.loads(gate_path.read_bytes())
        build=json.loads(build_path.read_bytes())
        assert build['qualification_exit_code']==0
        assert build['runtime_sha256']==identity['runtime_sha256']
        assert build['input_sources']['qualify_executor.py']==sha(ROOT/'source_port/qualify_executor.py')
        references['gate']=dict(path=str(gate_path),sha256=sha(gate_path),
            build=dict(path=str(build_path),sha256=sha(build_path)))
    assert gate_result['tests']==23 and not any(gate_result[n] for n in ('failures','errors','skips'))
    inputs={p.relative_to(ROOT).as_posix():sha(p) for pattern in
        ('conformance/checkpoint_error*','source_port/checkpoint_error_patches.py')
        for p in ROOT.glob(pattern) if p.is_file()}
    inputs['source_port/qualify_executor.py']=sha(ROOT/'source_port/qualify_executor.py')
    inputs['source_port/native/continuation.cpp']=sha(ROOT/'source_port/native/continuation.cpp')
    report=dict(schema_version=1,scope='Synchronous original procedure exception-unwind bookkeeping',
        runtime_image=candidate['runtime_image'],runtime_provenance=identity,inputs=inputs,evidence=references,
        corrected_exact_controls=corrected,
        passed_checks=dict(original_checkpoint_controls=24,additional_checkpoint_controls=20,
            native_ipc_regressions=4,existing_standalone_executor_gate=23),
        diagnosis='An exceptional RETURN retained the completed child model. The next LINE in its caller captured the dead child. Audit records actual frame, tracked frame, and model pointers.',
        correction='On a LINE in a known surviving ancestor, retire skipped child models and recorder frames through original return bookkeeping. Retain the original exceptional RETURN guard for uncaught errors.',
        unchanged_guards=['Continuation requires synchronous thread-owned frames',
            'Original error-mode RETURN retains uncaught error stack'],
        limitations=[
            'No new LRM clauses or general Python checkpoint support are qualified.',
            'Existing qualified PY rows retain imported-language evaluation scope and checkpoint_claim=false.',
            'Historical native host baseline used main#1 instead of the physical procedure source; all 8 retained baseline IPC controls failed before target recovery.',
            'This error-recorder report makes no live native IPC recovery claim; the separate checkpoint_identity evidence owns that scope. The historical blocker was not bypassed with a filesystem alias.',
            identity['limitation']],
        qualified_contracts=[],full_v05_accepted=False,full_v06_accepted=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output),passed_checks=report['passed_checks']),indent=2))


if __name__=='__main__':main()
