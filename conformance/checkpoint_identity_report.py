"""Qualify exact native checkpoint identity and context recovery evidence."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from checkpoint_identity_provenance import EXPECTED_SOURCES,qualification_identity
ERRORS=('module-error','named-error','nested-error','user-action-error')
RECOVERY=('normal','two-instances','kill-resume','changed-source','missing-wsp','empty-wsp',
    'corrupt-wsp','missing-asrun','empty-asrun','invalid-path','partial-stem')
MODES=('ON_LINE','ON_STEP')

REQUIRED_INPUTS = ('conformance/checkpoint_identity.Dockerfile',
 'conformance/checkpoint_identity.Dockerfile.dockerignore',
 'conformance/checkpoint_identity_build.py',
 'conformance/checkpoint_identity_install.py',
 'conformance/checkpoint_identity_ipc.py',
 'conformance/checkpoint_identity_provenance.py',
 'conformance/checkpoint_identity_recovery.py',
 'conformance/checkpoint_identity_run.py',
 'conformance/installed_provenance.py',
 'conformance/scdb_provenance.py',
 'distribution/incremental_native.py',
 'source_port/checkpoint_context_patches.py',
 'source_port/checkpoint_error_patches.py',
 'source_port/checkpoint_identity_patches.py')

def sha(raw):return hashlib.sha256(raw).hexdigest()


def read(path):
    path=Path(path)
    raw=path.read_bytes()
    return json.loads(raw),dict(path=str(path.resolve()),sha256=sha(raw))


def qualify_run(report,cases,kind):
    assert report['controller_exit_code']==0
    assert report['options']==dict(cases=list(cases),modes=list(MODES),kind=kind)
    assert set(report['checks'])=={mode+':'+case for mode in MODES for case in cases}
    for name,row in report['checks'].items():
        assert row['passed'] is True and name==row['mode']+':'+row['case'],name
        assert not any(row.get(key) for key in ('error','cleanup_error','extra_cleanup_error',
            'drain_error','sanitizer_failure')),name
    installed=report['runtime_sources'].get('profile') is not None
    from installed_provenance import input_paths
    expanded=set(REQUIRED_INPUTS)|set(input_paths(ROOT))|{'host_runtime/python/native.py'}
    assert set(report['inputs'])==expanded if installed else set(report['inputs']) in (set(REQUIRED_INPUTS),expanded)
    for name,expected in report['inputs'].items():
        assert sha((ROOT/name).read_bytes())==expected,name
    runtime=report['runtime_sources']
    identity=qualification_identity(runtime,report['inputs'],report.get('lf_normalized_inputs'))
    assert len(runtime['host_native_sha256'])==64
    return identity


def integrated_gates(directory,identity):
    if identity['kind']!='installed-composition':
        raise ValueError('Integrated gates require installed composition evidence')
    directory=Path(directory)
    artifacts=identity['native_artifacts']
    executor,executor_ref=read(directory/'executor-runtime.json')
    context,context_ref=read(directory/'context-runtime.json')
    eb,eb_ref=read(directory/'executor-build.json')
    cb,cb_ref=read(directory/'context-build.json')
    assert eb['qualification_exit_code']==cb['qualification_exit_code']==0
    assert eb['runtime_sha256']==artifacts['libspell_executor313.so']
    assert eb['command']['sha256']==artifacts['SPELL-ExecutorCmd_v3'] and eb['command']['link_exit_code']==0
    assert cb['executor_build_sha256']==eb_ref['sha256']
    assert set(cb['programs'])=={'SPELL_Context','SPELL_Listener','SPELL_Executor_v3','SPELL_Service_v3'}
    for name,program in cb['programs'].items():
        assert program['link_exit_code']==0 and all(row['exit_code']==0 for row in program['units']),name
        assert program['sha256']==artifacts[program['executable']],name
        if 'shared_runtime' in program:
            assert program['shared_runtime']['sha256']==artifacts['libspell_executor313.so']
    for name,build,count,gate in (('executor',eb,23,executor),('context',cb,10,context)):
        assert gate['tests']==count and not any(gate[key] for key in ('failures','errors','skips'))
        for source in ('qualify_'+name+'.py',name+'_build.py'):
            assert build['input_sources'][source]==sha((ROOT/'source_port'/source).read_bytes())
    for name,expected in EXPECTED_SOURCES.items():
        rows=cb['programs']['SPELL_Context']['units'] if '/SPELL_CTX/' in name else eb['units']
        matching=[row for row in rows if row['unit']==name]
        assert len(matching)==1 and matching[0]['exit_code']==0
        assert matching[0]['sha256']==expected['patched_sha256'],name
    assert context['service_checkpoint_rejections']==2 and context['selection']=='all'
    executor_ref['build']=eb_ref;context_ref['build']=cb_ref
    return (executor,executor_ref),(context,context_ref)


def compact(row):
    result={name:value for name,value in row.items() if name not in ('log','events')}
    for name in ('log','events'):
        if name in row:result[name+'_sha256']=sha(json.dumps(row[name],sort_keys=True).encode())
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-source','baseline-context','errors','recovery','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    for name in ('executor-gate','context-gate','integrated-gate-dir'):
        parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    source,source_ref=read(args.baseline_source)
    context,context_ref=read(args.baseline_context)
    errors,error_ref=read(args.errors)
    recovery,recovery_ref=read(args.recovery)
    identity=qualify_run(errors,ERRORS,'error-ipc')
    assert qualify_run(recovery,RECOVERY,'recovery')==identity
    assert errors['runtime_image']==recovery['runtime_image']
    if identity['kind']=='diagnostic-overlay':
        assert errors['runtime_sources']['baseline']==recovery['runtime_sources']['baseline']
    assert source['controller_exit_code']==context['controller_exit_code']==0
    assert len(source['checks'])==8
    assert set(source['checks'])=={mode+':'+case for mode in MODES for case in ERRORS}
    for row in source['checks'].values():
        assert not row['passed']
        if row['mode']=='ON_STEP':
            assert 'Source is unavailable: main#1' in str(row['error'])
        else:
            # Original ON_LINE capture fails before the host attaches. It proves
            # startup ERROR, but its exact native reason was not retained.
            assert 'Native procedure could not open' in row['error']
            assert "'ExecutorStatus': 'ERROR'" in row['error']
    assert len(context['checks'])==8
    for key,row in context['checks'].items():
        if row['case'] in ('normal','two-instances'):assert row['passed']
        else:assert not row['passed'] and 'Warmstart files missing' in str(row.get('error')),key
    if args.integrated_gate_dir:
        assert not args.executor_gate and not args.context_gate
        (executor,executor_ref),(service,service_ref)=integrated_gates(args.integrated_gate_dir,identity)
    else:
        assert args.executor_gate and args.context_gate and identity['kind']=='diagnostic-overlay'
        executor,executor_ref=read(args.executor_gate)
        service,service_ref=read(args.context_gate)
        overlay=identity['evidence']
        for gate,count,name in ((executor,23,'executor'),(service,10,'context')):
            assert gate['exit_code']==gate['controller_exit_code']==0
            assert gate['gate_name']==name and gate['gate']['tests']==count
            assert gate['gate']['failures']==gate['gate']['errors']==gate['gate']['skips']==0
            assert gate['overlay']==overlay
            assert gate['native_artifacts']==overlay['artifacts']
            assert gate['runtime_sha256']==overlay['artifacts']['libspell_executor313.so']
            assert gate['qualifier_sha256']==sha((ROOT/'source_port'/('qualify_'+name+'.py')).read_bytes())
            assert gate['controller_sha256']==sha((ROOT/'conformance/checkpoint_identity_gate.py').read_bytes())
        executor=executor['gate'];service=service['gate']
    assert service['service_checkpoint_rejections']==2
    report=dict(schema='openbexi.spell.checkpoint-identity/1',qualified_contracts=[],
        full_v05_accepted=False,full_v06_accepted=False,
        scope=['Original native procedure manager resolves checkpoint source exactly as prepareExecution',
            'Original instance IDs still name distinct checkpoints for a shared source',
            'Actual context kill/reopen restores nested synchronous state without replaying module effects',
            'Exact WSP/ASRUN preflight rejects invalid basenames and missing or empty files',
            'Actual recorder rejects CRC corruption and changed source with no effects',
            'Existing uncaught-error recovery and failing callback controls remain usable',
            'Original standalone23 and context10 gates preserve service recovery rejection'],
        exclusions=['Native service checkpoint recovery remains rejected',
            'Rejected warm startup emits fatal MSG_ERROR then may report UNINIT; stable terminal ERROR and recovery UI behavior are not qualified',
            'Live external resources, asynchronous or other-thread frame continuation remain unsupported',
            identity['limitation'],
            'Existing qualified PY language rows do not claim native checkpoint/recovery support'],
        runtime_image=errors['runtime_image'],runtime_sources=errors['runtime_sources'],runtime_provenance=identity,
        baseline_source=dict(evidence=source_ref,scope='ON_STEP4 explicitly report unavailable main#1 source; ON_LINE4 fail startup in ERROR before error detail is captured',checks={k:compact(v) for k,v in source['checks'].items()}),
        baseline_context=dict(evidence=context_ref,checks={k:compact(v) for k,v in context['checks'].items()}),
        native_errors=dict(evidence=error_ref,checks={k:compact(v) for k,v in errors['checks'].items()}),
        native_recovery=dict(evidence=recovery_ref,checks={k:compact(v) for k,v in recovery['checks'].items()}),
        standalone_gate=dict(evidence=executor_ref,gate=executor),
        context_gate=dict(evidence=service_ref,gate=service),
        inputs={**errors['inputs'],'conformance/checkpoint_identity_gate.py':sha((ROOT/'conformance/checkpoint_identity_gate.py').read_bytes()),
            'conformance/checkpoint_identity_report.py':sha(Path(__file__).read_bytes()),
            'conformance/checkpoint_identity_patch_test.py':sha((ROOT/'conformance/checkpoint_identity_patch_test.py').read_bytes())})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output.read_bytes()),
        errors=8,recovery=22,standalone=23,context=10,full_v06_accepted=False)))


if __name__=='__main__':main()
