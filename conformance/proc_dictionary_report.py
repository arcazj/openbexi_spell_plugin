"""Verify the PROC diagnostic against retained native observations and sources."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from proc_metadata_cases import CASES as BASELINE_CASES
from proc_lifecycle_cases import CASES as LIFECYCLE_CASES
from proc_dictionary_provenance import qualification_identity

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import validate_report
from evidence_sources import source_bytes
from installed_provenance import verify_capture

CANDIDATE_CONTRACTS=['CMP-LRM244-'+name for name in (
    'CONSTANT-PROC-KEY-ARGS','CONSTANT-PROC-KEY-INPUT-DATA','CONSTANT-PROC-KEY-NAME',
    'CONSTANT-PROC-KEY-OUTPUT-DATA','CONSTANT-PROC-KEY-PARENT',
    'CONSTANT-PROC-KEY-PREV-STEP','CONSTANT-PROC-KEY-STEP',
    'DATABASE-PROC','EXAMPLE-142','SECTION-4-15-4-099')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())


def reference(path):return dict(path=str(path.resolve()),sha256=sha(path))


def verify_cases(baseline_path,lifecycle_path,image,source_revision=None):
    raw=read(baseline_path);lifecycle=read(lifecycle_path)
    diagnostic=raw.get('diagnostic_overlay',False)
    inputs={};checks={}
    for path,report,cases,prefix in (
            (baseline_path,raw,BASELINE_CASES,'proc_metadata'),
            (lifecycle_path,lifecycle,LIFECYCLE_CASES,'proc_lifecycle')):
        validate_report(path,image,len(cases),source_revision=source_revision)
        assert report['passed'] and report.get('diagnostic_overlay',False)==diagnostic and not report['timed_out']
        assert set(report['checks'])==set(cases)
        if diagnostic:
            identity=qualification_identity(report['runtime_sources'],report['inputs'])
            assert identity==report['qualification_identity']
        else:
            assert source_revision is None, 'Fresh qualification must use current source inputs'
            verify_capture(report['runtime_sources']['integrated'],report['inputs'])
        assert report['host_inputs']=={p.name:sha(p) for p in (ROOT/'host_runtime/python').glob('*.py')}
        for name,digest in report['inputs'].items():
            assert inputs.get(name,digest)==digest,name
            inputs[name]=digest
        workspace=path.parent/'workspace'
        assert read(workspace/'checks.json')==report['checks']
        for name,digest in report.get('generated_sources',{}).items():assert sha(workspace/name)==digest,name
        assert sha(workspace/(prefix+'_cases.py'))==inputs['conformance/'+prefix+'_cases.py']
        expected=source_bytes(ROOT,'conformance/'+prefix+'_controller.py',source_revision)
        if diagnostic:
            expected=expected.replace(b'from installed_provenance import capture',b'from proc_dictionary_provenance import capture')
        assert (workspace/(prefix+'_controller.py')).read_bytes()==expected
        for name,spec in cases.items():
            row=deepcopy(report['checks'][name]);project=workspace/name.replace(':','-')
            assert row['passed'] and not any(k.endswith('_error') for k in row)
            assert row['dimension']==spec['dimension'] and row['source']==spec['source']
            assert (project/'main.py').read_text()==spec['source']
            assert sha(project/'native.log')==row['native_log_sha256']
            log=(project/'native.log').read_text()
            assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
            assert sha(project/'events.json')==row['events_sha256']
            events=read(project/'events.json')
            if prefix=='proc_metadata':
                observed=read(project/'observed.json');assert observed==row['observed']
                initial=observed['initial']
                assert row['status']=='FINISHED' and row['result']=={'metadata':True}
                assert observed['args_type']=='dict' and initial['ARGS']==spec['arguments']
                assert all(type(initial['ARGS'][k]) is type(v) for k,v in spec['arguments'].items())
                assert initial['NAME']=='main#1' and initial['PARENT']==''
                assert initial['STEP'] is None and initial['PREV_STEP'] is None
                assert observed['first']=={'step':['FIRST','Initial step'],'previous':None}
                assert observed['second']=={'step':['SECOND','Displayed step'],'previous':['FIRST','Initial step']}
                assert observed['custom']=={'A':[1,False,'caf\u00e9']} and observed['recovery']==42
                assert observed['errors']==['unhashable','missing']
            else:
                plan=read(project/'plan.json');assert plan==row['fixture_paths']
                for key in ('arguments','dimension','operation','rounds'):assert plan[key]==spec[key]
                remote='/workspace/'+name.replace(':','-')
                assert plan['input']==remote+'/fixture-inputs' and plan['output']==remote+'/fixture-outputs'
                assert (project/'fixture-inputs/input.txt').read_text()==plan['content']
                assert row['output_files']=={p.name:p.read_text() for p in (project/'fixture-outputs').glob('*.txt')}
                opened={e['message']['fields']['ProcId'] for e in events
                    if e.get('message',{}).get('id')=='MSG_EXEC_OP'
                    and e['message']['fields'].get('ExecOp')=='OPEN'
                    and e['message']['fields'].get('ParentId')=='main#1'}
                if spec['operation']=='child':
                    assert len(opened)==1
                    child_instance,=opened
                    assert child_instance.split('#',1)[0]=='child'
                expected_files={'main-1.txt',child_instance.replace('#','-')+'.txt'} if spec['operation']=='child' else {'main-1.txt'}
                assert row['output_files']=={name:plan['content'] for name in expected_files}
                assert sha(project/'context-configuration.xml')==row['configuration_sha256']
                config=ET.parse(project/'context-configuration.xml')
                assert config.find('input_dir').text=='$PROC_METADATA_INPUT'
                assert config.find('output_dir').text=='$PROC_METADATA_OUTPUT'
                assert sha(workspace/'configured-bin/spell-native')==row['launcher_sha256']
                for filename,digest in row['procedure_inputs'].items():assert sha(project/filename)==digest
                commands=[r['command'] for r in row['commands']]
                if spec['operation']=='child':
                    assert commands==['CMD_RUN']
                    assert (project/'child.py').read_text()==spec['child']
                    child=read(project/'child-result.json');parent=read(project/'parent-result.json')
                    assert child==row['child_result'] and parent==row['parent_result']
                    assert child['initial']['NAME']==child_instance
                    assert child['initial']['PARENT']==parent['initial']['NAME']=='main#1'
                    assert parent['initial']['PARENT']==''
                    assert child['initial']['ARGS']==spec['arguments'] and parent['initial']['ARGS']=={}
                    assert child['custom']=={'owner':'child'} and parent['initial']['PRIVATE_VALUE']=={'owner':'parent'}
                    assert child['first']=={'step':['CHILD','Child metadata'],'previous':None}
                    assert child['last']=={'step':['DONE','Child done'],'previous':['CHILD','Child metadata']}
                    assert opened=={child_instance}
                else:
                    separator=['CMD_RELOAD'] if spec['operation']=='reload' else ['REQ_CLOSE_EXEC','REQ_EXEC_LIST','REQ_OPEN_EXEC']
                    assert commands==['CMD_RUN']+(separator+['CMD_RUN'])*(spec['rounds']-1)
                    runs=read(project/'runs.json');assert len(runs)==len(row['phases'])==spec['rounds']
                    for phase,(observed,record) in enumerate(zip(runs,row['phases']),1):
                        assert record['observed']==observed and record['phase']==observed['phase']==phase
                        expected_count=phase if spec['operation']=='reopen' else 1
                        assert record['evaluations']==observed['evaluations']==expected_count
                        expected_error=(spec['dimension']=='failure' and phase==1 or spec['dimension']=='recovery' and phase<3)
                        assert record['status']==('ERROR' if expected_error else 'FINISHED')
                        assert observed['initial']['ARGS']==spec['arguments']
                        assert 'PRIVATE_VALUE' not in observed['initial']
                        assert observed['initial']['STEP'] is None and observed['initial']['PREV_STEP'] is None
                        assert observed['initial']['NAME']=='main#1' and observed['initial']['PARENT']==''
                    assert int((project/'evaluations.txt').read_text())==row['phases'][-1]['evaluations']
                    assert (project/'completed.txt').read_text()==str(spec['rounds'])
            row.update(contracts=[],oracle='LRM p81 procedure metadata and p90 input/output paths; native events, retained files and independent expression counter.')
            checks[name]=row
    for dimension in ('positive','boundary','failure','recovery'):
        dependencies=[key for key,row in checks.items() if row['dimension']==dimension]
        assert len(dependencies)==4
        checks['procedure-dictionary:'+dimension]=dict(passed=True,dimension=dimension,
            contracts=[],dependencies=dependencies,
            oracle='Root metadata, actual child metadata, reload and close/reopen must all pass independently.')
    return inputs,checks,raw


def qualify(baseline_path,lifecycle_path,original_path,image,source_revision=None):
    inputs,checks,raw=verify_cases(baseline_path,lifecycle_path,image,source_revision)
    assert raw['diagnostic_overlay']
    original=read(original_path)
    # Preserve a directly observed counterexample from the unchanged runtime.
    assert not original['passed'] and not original['timed_out']
    assert set(original['checks'])==set(BASELINE_CASES)
    assert original['runtime_sources']['integrated']==raw['runtime_sources']['baseline']
    for name,spec in BASELINE_CASES.items():
        row=original['checks'][name]
        project=original_path.parent/'workspace'/name.replace(':','-')
        assert row['source']==spec['source'] and not row['passed'] and row['status']=='ERROR'
        assert read(project/'observed.json')==row['observed']
        assert row['observed']['args_type']=='str' and isinstance(row['observed']['initial']['ARGS'],str)
        assert (project/'main.py').read_text()==spec['source']
    for name in ('conformance/proc_dictionary_report.py','tests/test_proc_dictionary_report.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,
        qualification_identity=raw['qualification_identity'],
        raw={name:reference(path) for name,path in (('baseline',baseline_path),('lifecycle',lifecycle_path),('original',original_path))},
        candidate_contracts=CANDIDATE_CONTRACTS,qualified_contracts=[],
        scope='Sixteen native diagnostic cases; fresh composed runtime qualification remains required',
        full_v05_accepted=False,full_v06_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','lifecycle','original'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    report=qualify(args.baseline,args.lifecycle,args.original,args.image)
    path=ROOT/'conformance/evidence/proc_dictionary.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(path),checks=len(report['checks']),qualified_contracts=0)))


if __name__=='__main__':main()
