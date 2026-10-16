"""Independently bind GetTM failure actions to packets, native prompts and RPCs."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'distribution'),str(ROOT/'driver_plugin/src')]
from evidence_sources import source_bytes
from run_language_regressions import validate_report
from telemetry_features_review import provenance,frozen
from dss.packets import decode_tm
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


def cases(revision):
    source=source_bytes(ROOT,'conformance/telemetry_policy_cases.py',revision)
    anchor=b'from telemetry_surface_cases import HEADER'
    assert source.count(anchor)==1
    module=types.ModuleType('_frozen_policy_cases')
    module.HEADER=frozen('conformance/telemetry_surface_cases.py',revision).HEADER
    exec(compile(source.replace(anchor,b''),'telemetry_policy_cases.py','exec'),module.__dict__)
    return module.CASES


def case_proof(name,spec,row,project):
    dimension=name.split(':')[1]
    assert row['passed'] and row['status']==spec['expected_status']
    assert not any(key.endswith('_error') for key in row)
    assert row['feature']=='failure-policy' and row['dimension']==dimension
    assert row['source']==spec['source']==(project/'main.py').read_text(encoding='utf-8')
    observed=read(project/'observed.json');assert observed==row['observed']
    assert all(item['actual']==item['expected'] for item in observed['observations'])
    calls=observed['calls'];assert len(calls)==(2 if dimension=='recovery' else 1)
    assert all(call['function']=='GetTM' and 'error' not in call for call in calls)
    if dimension=='failure':
        assert not (project/'result.json').exists() and 'result' not in row
        assert all('returned' not in call for call in calls)
    else:
        assert read(project/'result.json')==row['result']=={'completed':True}
        assert [call['returned'] for call in calls]==(['None','28.0'] if dimension=='recovery' else ['28.0'])
    assert sha(project/'native.log')==row['native_log_sha256']
    log=(project/'native.log').read_text(encoding='utf-8')
    assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
    assert sha(project/'events.json')==row['events_sha256']
    events=read(project/'events.json')
    assert not any(event.get('event')=='connectionError' for event in events)
    prompts=[event['message']['fields'] for event in events if event.get('message',{}).get('id')=='MSG_PROMPT']
    assert prompts==row['prompts'] and len(prompts)==len(spec['actions'])
    assert [answer['action'] for answer in row['answers']]==spec['actions']
    for index,(prompt,answer) in enumerate(zip(prompts,row['answers'])):
        assert prompt['ExpectedValues'].split('\x04')==['A','R','K']
        assert answer==dict(action=spec['actions'][index],choices=['ABORT','REPEAT','SKIP'],prompt=index)
    assert row['held']==[dict(status='PROMPT',returned=False)]*(3*len(prompts))
    assert row['states'][-1]['status']==spec['expected_status']
    assert row['receipts']==[]
    with sqlite3.connect((project/'dss.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        scenarios={key:dict(epoch=epoch,state=json.loads(state),faults=json.loads(faults))
            for key,epoch,state,faults in db.execute('SELECT id,epoch,state,faults FROM scenarios')}
        packets=[packet for packet, in db.execute('SELECT packet FROM packets')]
        assert db.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    initial=scenarios[row['initial_dss']['scenario_id']]
    assert initial['faults']['telemetry_quality']==spec['faults']['telemetry_quality']
    assert scenarios[row['final_dss']['scenario_id']]['state']==row['final_dss']
    controls=row['fixture_controls'];repairs=row['prompt_repairs']
    assert [record['command'] for record in controls]==[record['request'] for record in observed['fixtures']]
    assert len(controls)==(1 if dimension=='recovery' else 0)
    assert len(repairs)==(1 if spec['repair_after'] else 0)
    for record in controls+repairs:
        assert record['before']['epoch']!=record['after']['epoch']
        for when in ('before','after'):
            raw=bytes.fromhex(record[when+'_packet_hex']);assert raw in packets
            packet=decode_tm(raw)
            assert packet['scenario_id']==record[when]['scenario_id'] and packet['satellite_epoch']==record[when]['epoch']
        assert scenarios[record['after']['scenario_id']]['faults']['telemetry_quality']=='GOOD'
    if repairs:assert repairs[0]['prompt']==spec['repair_after']-1
    for record,saved in zip(controls,observed['fixtures']):
        command=record['command'];assert command['action']=='reset' and command['faults']=={}
        response=read(project/('fixture-'+command['token']+'.json'))
        assert response==saved['response'] and response['state']==record['after'] and response['packet_hex']==record['after_packet_hex']
    decoded=[decode_tm(packet) for packet in packets]
    responses=Counter();refreshes=[]
    for call in row['rpc']:
        service,method_name=call['path'].split('/')[1:]
        assert not service.endswith('_TC')
        method=p.DESCRIPTOR.services_by_name[service.removeprefix('spell.driver.')].methods_by_name[method_name]
        request_bytes=bytes.fromhex(call['request'])
        request=GetMessageClass(method.input_type).FromString(request_bytes)
        assert 'response' in call and 'error' not in call
        response_bytes=bytes.fromhex(call['response'])
        response=GetMessageClass(method.output_type).FromString(response_bytes)
        responses[(hashlib.sha256(call['path'].encode()+b'\0'+request_bytes).hexdigest(),response_bytes)]+=1
        if method_name=='RefreshItem':
            assert request.item.mnemonic=='TM.POWER.BUS_VOLTAGE'
            assert unpack(request.config).get('Wait') is False
            matches=[(packet,item) for packet in decoded for item in packet['items']
                if item['item_id']==request.item.mnemonic and item['raw']['value']==unpack(response.rawValue)
                and item['engineering']['value']==unpack(response.engValue)
                and datetime.fromtimestamp(packet['acquired_at_unix_ns']/1e9,timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')==response.timestamp]
            assert matches
            wanted='GOOD' if response.validity else spec['faults']['telemetry_quality']
            assert any(item['quality']==wanted and item['validity']=='VALID' and packet['synchronization_state']=='COMPLETE' for packet,item in matches)
            refreshes.append(dict(valid=response.validity,raw=unpack(response.rawValue),eng=unpack(response.engValue),timestamp=response.timestamp))
    expected={'positive':[False,True],'boundary':[False,False,True],'failure':[False],'recovery':[False,True]}[dimension]
    assert [item['valid'] for item in refreshes]==expected
    with sqlite3.connect((project/'driver.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        grounds=[json.loads(state) for state, in db.execute('SELECT state FROM ground')]
        journal=db.execute('SELECT digest,state,receipt FROM effects').fetchall()
    assert row['initial_ground'] in grounds and row['final_ground'] in grounds
    assert all(not value['limits'] and not value['injections'] and value['links']=={'TM':True,'TC':True} for value in grounds)
    for digest,state,receipt in journal:assert state=='RECEIPTED' and responses[(digest,receipt)]>0
    return dict(passed=True,dimension=dimension,actions=spec['actions'],held_observations=len(row['held']),
        refreshes=refreshes,repairs=len(repairs)+len(controls),terminal_status=row['status'],qualified_contracts=[])


def review(path,overlay,limit_overlay,revision,image):
    raw=read(path);specs=cases(revision)
    validate_report(path,image,4,source_revision=revision)
    assert raw['passed'] and not raw['timed_out'] and raw['controller_exit_code']==0
    assert raw['diagnostic_only'] and raw['qualified_contracts']==[] and set(raw['checks'])==set(specs)
    workspace=path.parent/'workspace'
    assert read(workspace/'checks.json')==raw['checks'] and read(workspace/'runtime.json')==raw['runtime_sources']
    assert raw['artifacts']=={p.relative_to(workspace).as_posix():sha(p) for p in workspace.rglob('*') if p.is_file()}
    for name,digest in raw['inputs'].items():
        assert sha(path.parent/'inputs'/name)==digest
        if name.startswith('src/dss/'):assert sha(workspace/'fixture'/name.removeprefix('src/'))==digest
    for name in ('telemetry_policy_cases.py','telemetry_policy_controller.py','telemetry_surface_cases.py','telemetry_features_provenance.py','installed_provenance.py'):
        assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    assert read(workspace/'host-inputs.json')==raw['host_inputs']
    provenance(raw,overlay,limit_overlay,revision)
    checks={name:case_proof(name,specs[name],row,workspace/name.replace(':','__')) for name,row in raw['checks'].items()}
    return dict(passed=True,runtime_image=image,source_revision=revision,raw=ref(path),checks=checks,
        overlay=str(overlay.resolve()),limit_overlay=str(limit_overlay.resolve()),
        review_source=ref(Path(__file__)),source_inputs=raw['inputs'],artifacts=raw['artifacts'],
        qualified_contracts=[],full_v05_accepted=False,scope='Four original GetTM failure actions; full composed telemetry mapping remains pending')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    for key in ('raw','overlay','limit-overlay','output'):parser.add_argument('--'+key,type=Path,required=True)
    for key in ('revision','image'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();result=review(args.raw,args.overlay,args.limit_overlay,args.revision,args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=4,output=str(args.output))))
