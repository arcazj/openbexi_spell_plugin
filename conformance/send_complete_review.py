"""Review Send limits, telemetry results, command frames and durable receipts."""
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,sys,types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'distribution'),str(ROOT/'driver_plugin/src'),str(ROOT/'src')]
from evidence_sources import source_bytes
from evidence_database import evidence_database
from installed_provenance import verify_capture
from telemetry_features_review import provenance as telemetry_provenance
from dss.packets import decode_tc,decode_tm
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass

sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_bytes())
ref=lambda path:dict(path=str(path.resolve()),sha256=sha(path))
encoded=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
VOLTAGE='TM.POWER.BUS_VOLTAGE'
MODE='TM.CORE.MODE'
STAGES=['TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT','ONBOARD_EXECUTION']
OUTCOMES=['ACCEPTED','LOADED','RELEASED','ACKNOWLEDGED','SUCCEEDED']


def frozen(name,revision):
    source=source_bytes(ROOT,name,revision);module=types.ModuleType('_send_review_'+Path(name).stem)
    if name.endswith('/send_complete_cases.py'):
        anchor=b'from memory_native_cases import HEADER';assert source.count(anchor)==1
        module.HEADER=frozen('conformance/memory_native_cases.py',revision).HEADER;source=source.replace(anchor,b'')
    exec(compile(source,name,'exec'),module.__dict__);return module


def overlay_proof(raw,overlay,telemetry,limits,revision):
    runtime=raw['runtime_sources'];assert runtime['profile']=='fresh-composed-limit-telemetry-send-complete-overlays/1'
    assert sha(overlay/'base.json')==runtime['base_sha256']
    base=read(overlay/'base.json');assert base['integrated']==runtime['integrated']
    telemetry_provenance(dict(runtime_sources=base,inputs=raw['inputs']),telemetry,limits,revision)
    record=runtime['overlay'];assert record['files']=={q.relative_to(overlay).as_posix():sha(q)
        for q in overlay.rglob('*') if q.is_file() and q.name!='base.json' and '__pycache__' not in q.parts}
    recipe=frozen('source_port/send_complete_patches.py',revision)
    assert sha(overlay/'send_complete_patches.py')==raw['inputs']['source_port/send_complete_patches.py']
    assert read(overlay/'manifest.json')==record['manifest'] and set(record['manifest'])==set(recipe.PREIMAGES)
    expected=dict(base['installed'])
    for name,row in record['manifest'].items():
        before,after=overlay/'original'/name,overlay/'patched'/name
        assert sha(before)==expected[name]==row['preimage_sha256']
        assert recipe.apply(name,before.read_bytes())==after.read_bytes()
        expected[name]=sha(after);assert expected[name]==row['sha256']
    assert runtime['installed']==expected


def thresholds(low,high):return dict(LoRed=low,LoYel=low,HiYel=high,HiRed=high)


def expected_limits(name):
    feature,dimension=name.split(':')
    if feature=='complex-send':return []
    if feature=='adjust-analog':
        rows=[thresholds(20,40)]
        if dimension!='failure':rows += [thresholds(-1.7e308,1.7e308),thresholds(28,28) if dimension=='boundary' else thresholds(27.5,28.5)]
    else:
        rows=[dict(Nominal=['NOMINAL'],Error=['FAULT'])]
        if dimension=='positive':rows += [dict(Nominal=['NOMINAL','SAFE']),dict(Nominal=['SAFE'],Error=[])]
        if dimension=='recovery':rows += [dict(Nominal=['NOMINAL','MISSING']),dict(Nominal=['NOMINAL'],Error=[])]
    return rows


def case_proof(name,spec,row,project):
    feature,dimension=name.split(':')
    assert row['passed'] is True and row['status']=='FINISHED' and row['states'][-1]['status']=='FINISHED'
    assert not any(k.endswith('_error') for k in row)
    assert row['source']==spec['source']==(project/'main.py').read_text(encoding='utf-8')
    assert row['feature']==feature and row['dimension']==dimension
    assert encoded(row['result'])==encoded(read(project/'result.json'))==encoded({'completed':True})
    observed=read(project/'observed.json');assert observed==row['observed']
    assert all(encoded(v['actual'])==encoded(v['expected']) for v in observed['observations'] if 'actual' in v)
    errors=[c for c in observed['calls'] if 'error_type' in c]
    expected_errors=int(feature!='complex-send' and dimension=='failure' or name=='adjust-analog:recovery')
    assert len(errors)==expected_errors and all(c['error_type']=='DriverException' for c in errors)
    sends=[(c['return_type'],ast.literal_eval(c['returned'])) for c in observed['calls'] if c['function']=='Send' and 'returned' in c]
    expected_sends=[] if expected_errors and dimension=='failure' else [('TmResult',True)]
    if name=='adjust-status:recovery':expected_sends=[('TmResult',False),('TmResult',True)]
    if feature=='complex-send' and dimension in ('failure','recovery'):
        expected_sends=[('bool',False)]+([('TmResult',True)] if dimension=='recovery' else [])
    assert sends==expected_sends
    details=[v for v in observed['observations'] if v.get('actual_type')=='TmResult']
    assert [v['actual'] for v in details]==[v for t,v in sends if t=='TmResult']
    for index,detail in enumerate(details):
        expected={('0: '+VOLTAGE if feature!='adjust-status' else '0: '+MODE):detail['actual']}
        if feature=='complex-send':expected['1: TM.CORE.TICK']=True
        assert detail['details']==expected
    assert sha(project/'native.log')==row['native_log_sha256'] and sha(project/'events.json')==row['events_sha256']
    log=(project/'native.log').read_bytes()
    assert all(v not in log for v in (b'AddressSanitizer:',b'runtime error:',b'Exception in thread'))
    assert not any(e.get('event')=='connectionError' or e.get('message',{}).get('id') in ('MSG_ERROR','MSG_PROMPT') for e in read(project/'events.json'))
    assert [v['request'] for v in observed['fixtures']]==[v['command'] for v in row['fixture_controls']]
    assert len(row['fixture_controls'])==1 and row['fixture_controls'][0]['command']['action']=='feed'
    executions=0 if dimension=='failure' else 2 if name=='adjust-status:recovery' else 1
    assert row['initial_dss']['core']['commands_executed']==0
    assert row['final_dss']['core']['commands_executed']==executions
    with evidence_database(project/'dss.sqlite') as db:
        stored=db.execute('SELECT request_hash,raw_tc,acknowledgement FROM operations ORDER BY rowid').fetchall()
        packets=[decode_tm(v) for v, in db.execute('SELECT packet FROM packets')]
        saved,=db.execute('SELECT state FROM scenarios WHERE id=?',(row['final_dss']['scenario_id'],)).fetchall()
        assert json.loads(saved[0])==row['final_dss']
    assert len(stored)==len(row['receipts'])==5*executions
    frames=[]
    for index,((digest,packet,ack),receipt) in enumerate(zip(stored,row['receipts'])):
        assert digest==receipt['request_hash'] and packet.hex()==receipt['packet_hex']
        assert hashlib.sha256(packet).hexdigest()==receipt['packet_sha256'] and json.loads(ack)==receipt['acknowledgement']
        frame=decode_tc(packet);answer=json.loads(ack)
        assert frame['stage']==answer['stage']==STAGES[index%5] and answer['outcome']==OUTCOMES[index%5]
        assert frame['element_id']==answer['element_id'] and frame['operation_id']==answer['operation_id']
        assert frame['satellite_epoch']==row['initial_dss']['epoch'] and frame['procedure_id']==name
        if index%5==0:frames.append(frame)
    members=['CMD1','CMD2'] if name=='adjust-status:recovery' else ['TC.SIMULATOR.SET_MODE'] if name=='adjust-status:positive' else ['CMDNAME'] if feature=='complex-send' else ['CMD1']
    assert [v['command_name'] for v in frames]==(members if executions else [])
    for frame in frames:
        args=frame['arguments']
        if feature=='complex-send':
            value=0 if dimension=='boundary' else 255
            assert args==[dict(name='ARG1',value=1.0,value_type='FLOAT',value_format='ENG',radix='DEC',encoded='1'),
                dict(name='ARG2',value=value,value_type='LONG',value_format='ENG',radix='HEX',encoded='0x0' if value==0 else '0xFF')]
        elif name=='adjust-status:positive':assert args==[dict(name='MODE',value='SAFE',value_type='STRING',value_format='ENG',radix='DEC',encoded='SAFE')]
        else:assert args==[]
    effects=Counter();limits=[];refreshes=[]
    for call in row['rpc']:
        service,method=call['path'].split('/')[1:]
        descriptor=p.DESCRIPTOR.services_by_name[service.removeprefix('spell.driver.')].methods_by_name[method]
        request_bytes=bytes.fromhex(call['request']);request=GetMessageClass(descriptor.input_type).FromString(request_bytes)
        if 'response' not in call:assert 'error' in call;continue
        assert 'error' not in call
        response_bytes=bytes.fromhex(call['response']);response=GetMessageClass(descriptor.output_type).FromString(response_bytes)
        if method in ('RaiseEvent','SetLimits','SendCommand'):
            effects[(hashlib.sha256(call['path'].encode()+b'\0'+request_bytes).hexdigest(),response_bytes)]+=1
        if method=='SetLimits':
            assert response.value is True
            item=VOLTAGE if feature=='adjust-analog' else MODE
            assert request.item.mnemonic==item
            body=unpack(request.set.limitset)
            assert body['LimitProfile']=='OPENBEXI_LIMITS_1' and body['Operation']=='Modify'
            settings=body['Settings'];assert set(settings)==({'Definition'} if not limits else {'Definition','Select'})
            if limits:assert settings['Select']=='ACTIVE'
            limits.append(settings['Definition'])
        elif method=='RefreshItem':
            matches=[(packet,item) for packet in packets for item in packet.get('items',[])
                if item['item_id']==request.item.mnemonic and item['engineering']['value']==unpack(response.engValue)
                and item['raw']['value']==unpack(response.rawValue)
                and datetime.fromtimestamp(packet['acquired_at_unix_ns']/1e9,timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')==response.timestamp]
            assert matches and response.validity is True
            assert any(item['validity']=='VALID' and item['quality']=='GOOD' and packet['synchronization_state']=='COMPLETE' for packet,item in matches)
            refreshes.append((request.item.mnemonic,unpack(response.engValue)))
    assert limits==expected_limits(name)
    expected=deepcopy(row['initial_ground'])
    if limits:
        item=VOLTAGE if feature=='adjust-analog' else MODE
        definition=dict(Active=True,Type='HARDSOFT') if feature=='adjust-analog' else dict(Active=True,Type='STATUS',Nominal=[],Warning=[],Error=[],Ignore=[])
        for limit in limits:definition.update(limit)
        expected['limit_definitions']={item:{'GENERIC':definition}}
        expected['limit_history']={item:{}}
        if feature=='adjust-analog':expected['limits'][item]={k:definition[k] for k in ('LoRed','LoYel','HiYel','HiRed')}
    assert encoded(expected)==encoded(row['final_ground'])
    if executions:
        assert refreshes
        assert row['final_dss']['core']['mode']==('SAFE' if name=='adjust-status:positive' else 'NOMINAL')
    with evidence_database(project/'driver.sqlite') as db:
        grounds=[json.loads(v) for v, in db.execute('SELECT state FROM ground')]
        journal=db.execute('SELECT authority,digest,state,receipt FROM effects').fetchall()
    assert grounds==[expected]
    actual=Counter()
    for authority,digest,state,receipt in journal:
        assert json.loads(authority)['definition']==name and state=='RECEIPTED'
        actual[(digest,receipt)]+=1
    assert actual==effects
    if name=='complex-send:positive':
        elapsed,=[v['send_elapsed'] for v in observed['observations'] if 'send_elapsed' in v]
        assert 10<=elapsed<30
    return dict(passed=True,dimension=dimension,executions=executions,api_failures=len(errors),
        limits=limits,result_types=[v[0] for v in sends],telemetry_samples=len(refreshes),receipts=sum(actual.values()),
        oracle='Literal limit transitions and return protocols agree with original-schema RPC, binary command/telemetry packets and immutable SQLite receipts')


def review(path,overlay,telemetry,limits,revision,image,*,native_wheel=None,driver_wheel=None):
    raw=read(path);workspace=path.parent/'workspace'
    assert raw['passed'] is True and raw['controller_exit_code']==0 and raw['timed_out'] is False and raw['runtime_image']==image
    specs=frozen('conformance/send_complete_cases.py',revision).CASES
    assert len(specs)==12 and set(raw['checks'])==set(specs)
    for name,digest in raw['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT,name,revision)).hexdigest()==digest and sha(path.parent/'inputs'/name)==digest
        if name.startswith('src/dss/'):assert sha(workspace/'fixture'/name.removeprefix('src/'))==digest
    assert raw['artifacts']=={q.relative_to(workspace).as_posix():sha(q) for q in workspace.rglob('*') if q.is_file()}
    assert read(workspace/'checks.json')==raw['checks'] and read(workspace/'runtime.json')==raw['runtime_sources']
    assert read(workspace/'host-inputs.json')==raw['host_inputs']
    for name in ('memory_native_cases.py','send_complete_cases.py','send_complete_controller.py','send_complete_provenance.py','installed_provenance.py'):
        assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    verify_capture(raw['runtime_sources']['integrated'],raw['inputs'])
    wheels=None
    if raw['runtime_sources']['profile']=='fresh-composed-send-complete-wheel/1':
        assert overlay is telemetry is limits is None and native_wheel is not None and driver_wheel is not None
        from limit_telemetry_sources import verify
        wheels=verify(raw,native_wheel,driver_wheel,profile='fresh-composed-send-complete-wheel/1',required_recipes=('send_complete_patches.py',))
    else:overlay_proof(raw,overlay,telemetry,limits,revision)
    checks={name:case_proof(name,specs[name],row,workspace/name.replace(':','__')) for name,row in raw['checks'].items()}
    return dict(passed=True,runtime_image=image,source_revision=revision,raw=ref(path),overlay=str(overlay.resolve()) if overlay else None,composed_wheels=wheels,
        telemetry_overlay=str(telemetry.resolve()) if telemetry else None,limit_overlay=str(limits.resolve()) if limits else None,checks=checks,
        review_source=ref(Path(__file__)),source_inputs=raw['inputs'],qualified_contracts=[],full_v05_accepted=False)
