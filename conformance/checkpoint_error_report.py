"""Bind the narrow exception-unwind correction to retained actual native evidence."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load(identifier,kind='checkpoint-error'):
    path=ROOT/'.qualification/v0.6'/kind/identifier/'result.json'
    return json.loads(path.read_bytes()),dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','audit','candidate','expanded','ipc-baseline','ipc-candidate','ipc-blocker','gate'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    reports={};references={}
    for key in ('baseline','audit','candidate','expanded','ipc_baseline','ipc_candidate','ipc_blocker','gate'):
        reports[key],references[key]=load(getattr(args,key),'checkpoint-error-gate' if key=='gate' else 'checkpoint-error')
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
    gate=reports['gate']
    assert gate['controller_exit_code']==gate['exit_code']==0
    assert gate['gate']['tests']==23 and not any(gate['gate'][n] for n in ('failures','errors','skips'))
    overlay=candidate['runtime_sources']['checkpoint_overlay']
    assert overlay['mode']=='fix'
    assert gate['runtime_sha256']==overlay['artifacts']['libspell_executor313.so']
    for name in ('expanded','ipc_candidate'):
        assert reports[name]['runtime_image']==candidate['runtime_image']
        assert reports[name]['runtime_sources']['checkpoint_overlay']==overlay
    for name,digest in overlay['recipes'].items():
        path=ROOT/('source_port' if name=='checkpoint_error_patches.py' else
            'distribution' if name=='incremental_native.py' else 'conformance')/name
        assert sha(path)==digest,name
    inputs={p.relative_to(ROOT).as_posix():sha(p) for pattern in
        ('conformance/checkpoint_error*','source_port/checkpoint_error_patches.py')
        for p in ROOT.glob(pattern) if p.is_file()}
    inputs['source_port/native/continuation.cpp']=sha(ROOT/'source_port/native/continuation.cpp')
    report=dict(schema_version=1,scope='Synchronous original procedure exception-unwind bookkeeping',
        runtime_image=candidate['runtime_image'],native_overlay=overlay,inputs=inputs,evidence=references,
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
            'Native host warmstart remains blocked independently: original recorder source identity is main#1 instead of the physical procedure file; 8 retained baseline IPC controls failed before target recovery.',
            'The source-identity blocker was not bypassed with a filesystem alias; live native IPC recovery is not claimed.',
            overlay['limitation']],
        qualified_contracts=[],full_v05_accepted=False,full_v06_accepted=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output),passed_checks=report['passed_checks']),indent=2))


if __name__=='__main__':main()
