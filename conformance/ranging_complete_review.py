"""Independent native ranging review: original RPCs, atomic receipts and state."""
import ast
from collections import Counter
from copy import deepcopy
import hashlib,json,sys,types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'distribution'),str(ROOT/'driver_plugin/src')]
from evidence_sources import source_bytes
from evidence_database import evidence_database
from installed_provenance import verify_capture
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass

sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_bytes())
ref=lambda path:dict(path=str(path.resolve()),sha256=sha(path))
encoded=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'))
PATHS=[['DSS-BBE-1','DSS-ANTENNA-1'],['DSS-BBE-2','DSS-ANTENNA-2']]
DEFAULTS={'frequency_hz':'1000000','integration_ms':'1000'}
MEANINGS={'READY':0,'RANGING':1,'CALIBRATING':3,'ERROR':2}
ERRORS={'dual':[0,2,1,1],'baseband-batch':[0,1,1,1],
        'baseband-format':[0,0,2,1],'status':[0,0,1,0],'schedule-dual':[0,0,1,1]}
DIMENSIONS=['positive','boundary','failure','recovery']
FINAL={
 'dual:positive':('RANGING',PATHS,False),'dual:boundary':('READY',[],False),
 'dual:failure':('READY',[],False),'dual:recovery':('RANGING',[PATHS[1]],False),
 'status:positive':('READY',[],False),'status:boundary':('ERROR',[],False),
 'status:failure':('MALFORMED',[],False),'status:recovery':('READY',[],False),
 'schedule-dual:positive':('RANGING',PATHS,False),'schedule-dual:boundary':('READY',[],False),
 'schedule-dual:failure':('RANGING',PATHS,True),'schedule-dual:recovery':('READY',[],True),
}
BANDS={
 'baseband-batch:positive':('DSS-BBE-1',{'frequency_hz':'2000000','integration_ms':'250'}),
 'baseband-batch:boundary':('DSS-BBE-2',{'frequency_hz':'1','integration_ms':'1000000000'}),
 'baseband-batch:recovery':('DSS-BBE-1',{'frequency_hz':'3000000','integration_ms':'500'}),
 'baseband-format:boundary':('DSS-BBE-1',{'frequency_hz':'1000000000'}),
 'baseband-format:recovery':('DSS-BBE-1',{'frequency_hz':'4000000'}),
}


def frozen(name,revision):
    module=types.ModuleType('_ranging_review_'+Path(name).stem)
    exec(compile(source_bytes(ROOT,name,revision),name,'exec'),module.__dict__)
    return module


def overlay_proof(raw,directory,revision):
    runtime=raw['runtime_sources'];assert runtime['profile']=='fresh-composed-wheel-plus-ranging-overlay/1'
    assert sha(directory/'base.json')==runtime['base_sha256']
    base=read(directory/'base.json')
    assert base['profile']=='fresh-composed-display-command-wheel/1' and base['integrated']==runtime['integrated']
    verify_capture(runtime['integrated'],raw['inputs'])
    overlay=runtime['overlay']
    assert overlay['files']=={q.relative_to(directory).as_posix():sha(q) for q in directory.rglob('*')
        if q.is_file() and q.name!='base.json' and '__pycache__' not in q.parts}
    recipe=frozen('source_port/ranging_complete_patches.py',revision)
    assert sha(directory/'ranging_complete_patches.py')==raw['inputs']['source_port/ranging_complete_patches.py']
    assert read(directory/'manifest.json')==overlay['manifest']
    assert set(overlay['manifest'])==set(recipe.PREIMAGES)
    expected=dict(base['installed'])
    for name,row in overlay['manifest'].items():
        before,after=directory/'original'/name,directory/'patched'/name
        assert sha(before)==expected[name]==row['preimage_sha256']
        assert recipe.apply(name,before.read_bytes())==after.read_bytes()
        expected[name]=sha(after);assert expected[name]==row['sha256']
    assert set(overlay['added_sources'])=={'openbexi_dss_proxy/ranging_complete.py','openbexi_spell_dss/ranging_complete.py'}
    for name,digest in overlay['added_sources'].items():
        assert name not in expected and sha(directory/'modules'/name)==digest==raw['inputs']['driver_plugin/src/'+name]
        expected[name]=digest
    assert runtime['installed']==expected


def case_proof(name,spec,row,project):
    feature,dimension=name.split(':')
    assert row['passed'] is True and row['status']=='FINISHED' and row['states'][-1]['status']=='FINISHED'
    assert not any(key.endswith('_error') for key in row)
    assert row['dimension']==spec['dimension']==dimension
    assert row['source']==spec['source']==(project/'main.py').read_text(encoding='utf-8')
    assert encoded(row['result'])==encoded(read(project/'result.json'))==encoded({'completed':True})
    observed=read(project/'observed.json');assert observed==row['observed']
    assert all(encoded(v['actual'])==encoded(v['expected']) for v in observed['observations'])
    errors=[v for v in observed['calls'] if 'error_type' in v]
    assert len(errors)==ERRORS[feature][DIMENSIONS.index(dimension)]
    assert all(v['error_type']=='DriverException' for v in errors if not (name=='dual:boundary' and v is errors[1]))
    if name=='dual:boundary':assert errors[1]['error_type']=='SyntaxException'
    assert sha(project/'native.log')==row['native_log_sha256']
    log=(project/'native.log').read_text(encoding='utf-8')
    assert all(s not in log for s in ('AddressSanitizer:','runtime error:','Exception in thread'))
    assert sha(project/'events.json')==row['events_sha256']
    assert not any(e.get('event')=='connectionError' or e.get('message',{}).get('id') in ('MSG_ERROR','MSG_PROMPT') for e in read(project/'events.json'))
    assert row['initial_dss']==row['final_dss'] and row['initial_packet_hex']==row['final_packet_hex'] and row['receipts']==[]
    initial=deepcopy(row['initial_ground'])
    assert initial['ranging']=='READY' and initial['ranging_paths']==[] and initial['ranging_schedule_enabled'] is False
    assert initial['baseband']=={pair[0]:DEFAULTS for pair in PATHS}
    expected=deepcopy(initial)
    expected['ranging'],expected['ranging_paths'],expected['ranging_schedule_enabled']=FINAL.get(name,('READY',[],False))
    if name in BANDS:
        band,updates=BANDS[name];expected['baseband'][band].update(updates)
    assert encoded(row['final_ground'])==encoded(expected)
    model=deepcopy(initial)
    controls=row['fixture_controls']
    assert len(controls)==(1 if name in ('status:boundary','status:failure','status:recovery') else 0)
    assert [c['command'] for c in controls]==[c['request'] for c in observed['fixtures']]
    for control,saved in zip(controls,observed['fixtures']):
        command=control['command'];value='MALFORMED' if dimension=='failure' else 'ERROR'
        assert command==dict(action='ranging-state',value=value,token=command['token'])
        assert control['before']==control['after']==row['initial_dss']
        assert control['before_packet_hex']==control['after_packet_hex']==row['initial_packet_hex']
        assert control['ground_before']==initial
        model['ranging']=value;assert control['ground_after']==model
        assert read(project/('fixture-'+command['token']+'.json'))==saved['response']==dict(state=row['initial_dss'],ground=model,packet_hex=row['initial_packet_hex'])
    receipts=Counter();successful=[];failed_rpc=0
    for call in row['rpc']:
        service,method=call['path'].split('/')[1:]
        descriptor=p.DESCRIPTOR.services_by_name[service.removeprefix('spell.driver.')].methods_by_name[method]
        request_bytes=bytes.fromhex(call['request']);request=GetMessageClass(descriptor.input_type).FromString(request_bytes)
        assert service.endswith(('_RNG','_EV'))
        if 'response' not in call:
            assert service.endswith('_RNG') and 'error' in call;failed_rpc+=1;continue
        assert 'error' not in call
        response_bytes=bytes.fromhex(call['response']);response=GetMessageClass(descriptor.output_type).FromString(response_bytes)
        effect=service.endswith('_EV') or method in ('StartRanging','StartCalibration','AbortRanging','EnableRanging','DisableRanging','SetBasebandConfig')
        if effect:receipts[(hashlib.sha256(call['path'].encode()+b'\0'+request_bytes).hexdigest(),response_bytes)]+=1
        if service.endswith('_EV'):assert method=='RaiseEvent';continue
        wire=unpack(request.config) if hasattr(request,'config') and request.config.type_url else {}
        if method in ('StartRanging','StartCalibration'):
            paths=wire.get('Paths',[[request.bbe,request.antenna]])
            assert 1<=len(paths)<=2 and all(pair in PATHS for pair in paths) and len({pair[0] for pair in paths})==len(paths)
            if 'Paths' in wire:assert set(wire)=={'Paths'} and request.bbe==request.antenna==''
            else:assert wire=={}
            model['ranging']='RANGING' if method=='StartRanging' else 'CALIBRATING';model['ranging_paths']=paths
        elif method=='AbortRanging':
            assert wire=={} and request.bbe==request.antenna==''
            model['ranging']='READY';model['ranging_paths']=[]
        elif method in ('EnableRanging','DisableRanging'):
            assert wire=={} and request.bbe==request.antenna==''
            model['ranging_schedule_enabled']=method=='EnableRanging'
        elif method=='SetBasebandConfig':
            pairs=wire.get('Parameters',[[request.param,request.value]])
            assert request.bbe in model['baseband'] and 1<=len(pairs)<=2 and len({pair[0] for pair in pairs})==len(pairs)
            if 'Parameters' in wire:assert set(wire)=={'Parameters'} and request.param==request.value==''
            else:assert wire=={}
            for key,value in pairs:
                assert key in DEFAULTS and type(value) is str and value.isascii() and value.isdigit() and 1<=int(value)<=1000000000
                model['baseband'][request.bbe][key]=value
        elif method=='GetBasebandConfig':
            assert set(wire)<={'ValueFormat'} and wire.get('ValueFormat','Eng format') in ('Raw format','Eng format','Default format')
            assert response.bbe==request.bbe and response.param==request.param and response.value==model['baseband'][request.bbe][request.param]
        elif method=='GetRangingStatus':assert response.value==model['ranging'] and response.value in MEANINGS
        else:raise AssertionError('Unexpected ranging RPC: '+method)
        value=MEANINGS[response.value] if method=='GetRangingStatus' else response.value
        if effect:assert value is True
        successful.append(('StartRangingCalibration' if method=='StartCalibration' else method,value))
    native=[v for v in observed['calls'] if 'returned' in v]
    assert len(native)==len(successful)
    for call,(function,value) in zip(native,successful):
        assert call['function']==function and call['return_type']==type(value).__name__
        assert type(ast.literal_eval(call['returned'])) is type(value) and ast.literal_eval(call['returned'])==value
    assert model==expected and failed_rpc<=len(errors)
    with evidence_database(project/'driver.sqlite') as db:
        grounds=[json.loads(state) for state, in db.execute('SELECT state FROM ground')]
        journal=db.execute('SELECT authority,digest,state,receipt FROM effects').fetchall()
    assert grounds==[expected]
    actual=Counter()
    for authority,digest,state,receipt in journal:
        identity=json.loads(authority);assert identity['definition']==name and identity['mode']=='Development'
        assert state=='RECEIPTED';actual[(digest,receipt)]+=1
    assert actual==receipts
    with evidence_database(project/'dss.sqlite') as db:
        assert db.execute('SELECT count(*) FROM operations').fetchone()[0]==0
        assert bytes.fromhex(row['initial_packet_hex']) in [packet for packet, in db.execute('SELECT packet FROM packets')]
    return dict(passed=True,dimension=dimension,api_failures=len(errors),rpc_failures=failed_rpc,receipts=sum(actual.values()),
        ranging=expected['ranging'],paths=expected['ranging_paths'],schedule_enabled=expected['ranging_schedule_enabled'],
        oracle='Native return types, unchanged DSS, original protobuf, exact journal receipts and independently calculated ranging state')


def review(path,overlay,revision,image):
    raw=read(path);workspace=path.parent/'workspace'
    assert raw['passed'] is True and raw['controller_exit_code']==0 and raw['timed_out'] is False and raw['runtime_image']==image
    specs=frozen('conformance/ranging_complete_cases.py',revision).CASES
    assert len(specs)==20 and set(raw['checks'])==set(specs)
    for name,digest in raw['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT,name,revision)).hexdigest()==digest
        assert sha(path.parent/'inputs'/name)==digest
        if name.startswith('src/dss/'):assert sha(workspace/'fixture'/name.removeprefix('src/'))==digest
    assert raw['artifacts']=={q.relative_to(workspace).as_posix():sha(q) for q in workspace.rglob('*') if q.is_file()}
    assert read(workspace/'checks.json')==raw['checks'] and read(workspace/'runtime.json')==raw['runtime_sources']
    assert read(workspace/'host-inputs.json')==raw['host_inputs']
    for name in ('ranging_complete_cases.py','ranging_candidate_controller.py','installed_provenance.py','ranging_complete_provenance.py'):
        assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    overlay_proof(raw,overlay,revision)
    checks={name:case_proof(name,specs[name],row,workspace/name.replace(':','__')) for name,row in raw['checks'].items()}
    return dict(passed=True,runtime_image=image,source_revision=revision,raw=ref(path),overlay=str(overlay.resolve()),checks=checks,
        review_source=ref(Path(__file__)),source_inputs=raw['inputs'],qualified_contracts=[],full_v05_accepted=False)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    for key in ('raw','overlay','output'):parser.add_argument('--'+key,type=Path,required=True)
    for key in ('revision','image'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();result=review(args.raw,args.overlay,args.revision,args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,checks=len(result['checks']),output=str(args.output))))
