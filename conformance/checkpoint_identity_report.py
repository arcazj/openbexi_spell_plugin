"""Qualify exact native checkpoint identity and context recovery evidence."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
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
EXPECTED_SOURCES = {'lib/SPELL_CTX/src/SPELLcontext.C': {'original_sha256': 'cf4576a8a95c543cddd53b8cb4f136a53e0114c1fc5bf3ebd6e39b1c0ff9129c',
                                      'patched_sha256': '18a6e1ac5a7556232df381b5084d615d91756a4bbdfa2a18aa2fb672108d18d7',
                                      'ported_sha256': '9618798e11004db0d42422b16806c3a7fbe0c53ebbe8a2bba05fa5e410940b81'},
 'lib/SPELL_EXC/src/SPELLframeManager.C': {'original_sha256': 'ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402',
                                           'patched_sha256': 'b0e8757c78d15479ec88d22497bbbef7706a70b41954211d44cebde6c6a4d9a7',
                                           'ported_sha256': '31e1b73109a6266817f26ea0d1ad67935d81854c9e34c314aab75b33bda41fcf'},
 'lib/SPELL_EXC/src/SPELLinterpreter.C': {'original_sha256': '3dd0a455669237924726637ca4b25ae524acfaf10d577b18a7c36258ad3f1256',
                                          'patched_sha256': '3365e1e1f0ae0c697e9dd7152ad8fd2d4d0b7e0f0f04b73ba82d3cafb165aade',
                                          'ported_sha256': '670726c1853be672353f5e35da579d0e1c1569ab457d7c0cfe3d4c29692e3b33'}}

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
    assert set(report['inputs'])==set(REQUIRED_INPUTS)
    for name,expected in report['inputs'].items():
        assert sha((ROOT/name).read_bytes())==expected,name
    runtime=report['runtime_sources']
    overlay=runtime['identity_overlay']
    assert overlay['sources']==EXPECTED_SOURCES
    assert overlay['mode']=='identity'
    assert set(overlay['artifacts'])=={'libspell_executor313.so','SPELL-Context'}
    for name,expected in overlay['original_artifacts'].items():
        assert runtime['baseline']['native_artifacts'][name]==expected
        assert overlay['artifacts'][name]!=expected
    recipes={'checkpoint_identity_patches.py':'source_port/checkpoint_identity_patches.py',
        'checkpoint_context_patches.py':'source_port/checkpoint_context_patches.py',
        'checkpoint_error_patches.py':'source_port/checkpoint_error_patches.py',
        'checkpoint_identity_build.py':'conformance/checkpoint_identity_build.py',
        'incremental_native.py':'distribution/incremental_native.py'}
    assert overlay['recipes']=={name:report['inputs'][path] for name,path in recipes.items()}
    assert len(runtime['host_native_sha256'])==64
    return overlay


def compact(row):
    result={name:value for name,value in row.items() if name not in ('log','events')}
    for name in ('log','events'):
        if name in row:result[name+'_sha256']=sha(json.dumps(row[name],sort_keys=True).encode())
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-source','baseline-context','errors','recovery','executor-gate','context-gate','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    source,source_ref=read(args.baseline_source)
    context,context_ref=read(args.baseline_context)
    errors,error_ref=read(args.errors)
    recovery,recovery_ref=read(args.recovery)
    executor,executor_ref=read(args.executor_gate)
    service,service_ref=read(args.context_gate)
    overlay=qualify_run(errors,ERRORS,'error-ipc')
    assert qualify_run(recovery,RECOVERY,'recovery')==overlay
    assert errors['runtime_image']==recovery['runtime_image']
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
    for gate,count,name in ((executor,23,'executor'),(service,10,'context')):
        assert gate['exit_code']==gate['controller_exit_code']==0
        assert gate['gate_name']==name and gate['gate']['tests']==count
        assert gate['gate']['failures']==gate['gate']['errors']==gate['gate']['skips']==0
        assert gate['overlay']==overlay
        assert gate['native_artifacts']==overlay['artifacts']
        assert gate['runtime_sha256']==overlay['artifacts']['libspell_executor313.so']
        assert gate['qualifier_sha256']==sha((ROOT/'source_port'/('qualify_'+name+'.py')).read_bytes())
        assert gate['controller_sha256']==sha((ROOT/'conformance/checkpoint_identity_gate.py').read_bytes())
    assert service['gate']['service_checkpoint_rejections']==2
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
            'Diagnostic overlay retains original package RECORD; distribution acceptance requires a fresh composed build',
            'Existing qualified PY language rows do not claim native checkpoint/recovery support'],
        runtime_image=errors['runtime_image'],runtime_sources=errors['runtime_sources'],
        baseline_source=dict(evidence=source_ref,scope='ON_STEP4 explicitly report unavailable main#1 source; ON_LINE4 fail startup in ERROR before error detail is captured',checks={k:compact(v) for k,v in source['checks'].items()}),
        baseline_context=dict(evidence=context_ref,checks={k:compact(v) for k,v in context['checks'].items()}),
        native_errors=dict(evidence=error_ref,checks={k:compact(v) for k,v in errors['checks'].items()}),
        native_recovery=dict(evidence=recovery_ref,checks={k:compact(v) for k,v in recovery['checks'].items()}),
        standalone_gate=dict(evidence=executor_ref,gate=executor['gate']),
        context_gate=dict(evidence=service_ref,gate=service['gate']),
        inputs={**errors['inputs'],'conformance/checkpoint_identity_gate.py':sha((ROOT/'conformance/checkpoint_identity_gate.py').read_bytes()),
            'conformance/checkpoint_identity_report.py':sha(Path(__file__).read_bytes()),
            'conformance/checkpoint_identity_patch_test.py':sha((ROOT/'conformance/checkpoint_identity_patch_test.py').read_bytes())})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output.read_bytes()),
        errors=8,recovery=22,standalone=23,context=10,full_v06_accepted=False)))


if __name__=='__main__':main()
