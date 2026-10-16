"""Join native typed, client-editing and child-argument proofs for ARGS/IVARS."""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from child_arguments_report import qualify as qualify_children
from installed_provenance import verify_capture
from run_dta import item_matches

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution'))
from run_language_regressions import validate_report

CONTRACTS=['CMP-LRM244-DATA-CONTAINER-ARGS','CMP-LRM244-DATA-CONTAINER-IVARS']
DIMENSIONS=('positive','boundary','failure','recovery')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())


def qualify(dta_path,ipc_path,child_path,image):
    dta=read(dta_path);ipc=read(ipc_path);child=qualify_children(child_path)
    inputs={};checks={}
    for prefix,path,report,minimum in (
            ('dta',dta_path,dta,68),('ipc',ipc_path,ipc,64),('child',child_path,child,10)):
        validate_report(path,image,minimum)
        assert report.get('controller_exit',report.get('controller_exit_code'))==0
        assert len(report['checks'])==minimum
        verify_capture(report['runtime_sources']['integrated'],report['inputs'],report.get('lf_normalized_inputs'))
        for name,digest in report['inputs'].items():
            assert inputs.get(name,digest)==digest,name
            inputs[name]=digest
        for name,row in report['checks'].items():
            assert row['passed'] and not any(k.endswith('_error') for k in row)
            checks[prefix+':'+name]=dict(deepcopy(row),contracts=[])
    # Reconstruct the typed-container verdicts from retained native messages.
    folder=dta_path.parent
    assert sha(folder/'dta_contracts.py')==inputs['conformance/dta_contracts.py']
    assert sha(folder/'controller.py')==inputs['conformance/dta_controller.py']
    assert read(folder/'dta-complete.json')=={'complete':True}
    original=read(folder/'dta-results.json')
    assert set(original['checks'])==set(dta['checks'])
    messages=[e.get('message',{}) for e in read(folder/'dta-wire.json')]
    items=[m['fields'] for m in messages if m.get('id')=='MSG_NOTIFICATION' and m.get('fields',{}).get('DataType')=='ITEM']
    answers=read(folder/'dta-answers.json')
    for name,row in dta['checks'].items():
        assert original['checks'][name]['passed']
        expected=original['checks'][name]['expected']
        selected=[i for i in items if i.get('ItemName','').startswith('DTA:'+name+':')]
        assert selected==row['items']
        actual_answers=[a for a in answers if a['check']==name]
        assert actual_answers==row['controller_answers'] and len(actual_answers)==len(expected['prompts'])
        for wanted in expected['items']:assert any(item_matches(actual,wanted) for actual in selected)
        for variable,sequence in expected['sequences'].items():
            assert [[v.get('ItemStatus'),v.get('ItemValue')] for v in selected if v.get('ItemName')==variable]==sequence
    # Real native dictionary IPC must expose both automatically created typed
    # containers, reject invalid updates, and resume the unchanged procedure.
    workspace=ipc_path.parent/'workspace'
    assert sha(workspace/'controller.py')==inputs['conformance/dta_edit_controller.py']
    tree=ast.parse((workspace/'controller.py').read_text())
    source=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='source' for t in n.targets))
    assert (workspace/'main.py').read_text()==source
    assert "assert len(ARGS) == 0 and len(IVARS) == 0" in source
    result=read(workspace/'dta-edit-results.json')
    for key,value in result.items():assert ipc[key]==value,key
    assert ipc['passed'] and ipc['resumed_status']=='FINISHED' and ipc['continued_after_edits']
    assert (workspace/'complete.txt').read_text()=='complete'
    assert not (workspace/'should-not-evaluate.txt').exists()
    types=read(workspace/'container-types.json')
    assert set(types)=={'ARGS','IVARS'} and all('DataContainer' in value for value in types.values())
    native=(workspace/'native.log').read_text()
    assert 'AddressSanitizer:' not in native and 'runtime error:' not in native
    assert ipc['runtime_host_sha256']==ipc['runtime_sources']['host_sha256']==sha(ROOT/'host_runtime/python/native.py')
    observations=ipc['observations']
    assert len(observations)==240
    for container in ('ARGS','IVARS'):
        commands=[o for o in observations if o['fields'].get('DictName')==container]
        for dimension in DIMENSIONS:
            actual=ipc['checks'][container+':'+dimension]['actual']
            assert any(o['result']==actual for o in commands),(container,dimension)
        assert ipc['checks'][container+':failure']['actual'].get('Error') is True
        assert ipc['checks'][container+':positive']['actual']['DictContents'].split('\x04')[0].split('\x05')[:2]==['count','3']
        final=ipc['checks'][container+':recovery']['actual']['DictContents'].split('\x04')
        assert [entry.split('\x05')[:2] for entry in final]==[['count','7'],['text','caf\u00e9 \u03bb']]
        assert any(o['id']=='REQ_UPD_DICTIONARY' and o['fields'].get('DictMergeNew')=='True'
            and not o['result'].get('Error') for o in commands)
    wire=read(workspace/'dta-edit-wire.json')
    notifications=[e['message']['fields'] for e in wire if e.get('message',{}).get('id')=='MSG_NOTIFICATION'
        and e['message']['fields'].get('DataType')=='ITEM' and e['message']['fields'].get('ItemName')=='count'
        and e['message']['fields'].get('ItemValue')=='8']
    assert notifications==ipc['checks']['notifications:recovery']['actual']
    assert [n['ItemStatus'] for n in notifications]==['IN PROGRESS','SUCCESS','SUCCESS']*2
    for container,contract in zip(('ARGS','IVARS'),CONTRACTS):
        for dimension in DIMENSIONS:
            dependencies=[key for key,row in checks.items() if row['dimension']==dimension
                and (key.startswith('dta:') or key.startswith('ipc:'+container+':')
                     or container=='ARGS' and key.startswith('child:'))]
            if dimension=='recovery':dependencies+=['ipc:resume:recovery','ipc:notifications:recovery']
            assert len(dependencies)>=18
            checks[container.lower()+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[contract],dependencies=dependencies,
                oracle='LRM pp84-86 and89: real automatically created native DataContainer, independent typed operations, native client reads/edits, rejected edits and recovery; ARGS also requires actual parent-to-child transfer.')
    for name in ('conformance/predefined_containers_report.py','conformance/PREDEFINED_CONTAINERS.md','tests/test_predefined_containers_report.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,qualified_contracts=CONTRACTS,
        raw={name:dict(path=str(path.resolve()),sha256=sha(path)) for name,path in (
            ('dta',dta_path),('ipc',ipc_path),('child',child_path))},
        scope='Predefined typed ARGS and IVARS containers; original native runtime and client IPC',
        limitations=['Explicit spell.runtime imports; graphical presentation of client editing is a later installed-host gate',
            'No additional whole Var, StartProc or procedure-database contracts are allocated'],
        full_v05_accepted=False,full_v06_accepted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('dta','ipc','child'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--image',required=True)
    a=p.parse_args();report=qualify(a.dta,a.ipc,a.child,a.image)
    out=ROOT/'conformance/evidence/predefined_containers.json'
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(out),checks=len(report['checks']),contracts=len(CONTRACTS))))


if __name__=='__main__':main()
