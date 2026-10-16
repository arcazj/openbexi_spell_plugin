"""Independently check memory packets, ASCII files, catalog rows and receipts."""
import ast
from collections import Counter
from copy import deepcopy
import hashlib,json,sys,types,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'distribution'),str(ROOT/'driver_plugin/src'),str(ROOT/'src')]
from evidence_sources import source_bytes
from evidence_database import evidence_database
from telemetry_features_review import provenance as telemetry_provenance
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass
from dss.packets import decode_tm

sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_bytes())
ref=lambda path:dict(path=str(path.resolve()),sha256=sha(path))
encoded=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'))
ERRORS={'lookup-missing-recovery':1,'tmtc-range-failure':1,'packet-range-failure':2,'packet-missing-recovery':1,
 'report:failure':3,'report:recovery':1,'compare:failure':3,'compare:recovery':1,
 'lookup:failure':3,'lookup:recovery':1,'tmtc:failure':3,'tmtc:recovery':1}


def frozen(name,revision):
    module=types.ModuleType('_memory_review_'+Path(name).stem)
    source=source_bytes(ROOT,name,revision)
    if name.endswith('/memory_complete_cases.py'):
        anchor=b'from memory_native_cases import CASES as BASELINE,HEADER'
        assert source.count(anchor)==1
        base=frozen('conformance/memory_native_cases.py',revision)
        module.BASELINE,module.HEADER=base.CASES,base.HEADER;source=source.replace(anchor,b'')
    exec(compile(source,name,'exec'),module.__dict__)
    return module


def overlay_proof(raw,directory,telemetry,limits,revision):
    runtime=raw['runtime_sources'];assert runtime['profile']=='fresh-composed-limit-telemetry-memory-overlays/1'
    assert sha(directory/'base.json')==runtime['base_sha256']
    base=read(directory/'base.json');assert base['integrated']==runtime['integrated']
    telemetry_provenance(dict(runtime_sources=base,inputs=raw['inputs']),telemetry,limits,revision)
    record=runtime['overlay']
    assert record['files']=={q.relative_to(directory).as_posix():sha(q) for q in directory.rglob('*')
        if q.is_file() and q.name!='base.json' and '__pycache__' not in q.parts}
    recipe=frozen('source_port/memory_feature_patches.py',revision)
    assert sha(directory/'memory_feature_patches.py')==raw['inputs']['source_port/memory_feature_patches.py']
    assert set(record['manifest'])==set(recipe.PREIMAGES) and read(directory/'manifest.json')==record['manifest']
    expected=dict(base['installed'])
    for name,row in record['manifest'].items():
        before,after=directory/'original'/name,directory/'patched'/name
        assert sha(before)==expected[name]==row['preimage_sha256']
        assert recipe.apply(name,before.read_bytes())==after.read_bytes()
        expected[name]=sha(after);assert expected[name]==row['sha256']
    assert set(record['added_sources'])=={'openbexi_dss_proxy/memory_support.py','openbexi_spell_dss/memory_images.py'}
    for name,value in record['added_sources'].items():
        assert name not in expected and sha(directory/'modules'/name)==value==raw['inputs']['driver_plugin/src/'+name]
        expected[name]=value
    assert runtime['installed']==expected


def selected(record,catalog,begin='',end='',name='',address='',raw=False):
    low=0 if begin=='' else int(begin,16 if str(begin).lower().startswith('0x') else 10)
    high=0xffffffff if end=='' else int(end,16 if str(end).lower().startswith('0x') else 10)
    if address!='':low=high=int(address,16 if str(address).lower().startswith('0x') else 10)
    assert 0<=low<=high<=0xffffffff
    values=[]
    for item in decode_tm(bytes.fromhex(record['packet_hex']))['items']:
        code=catalog[item['item_id']]['item_code']
        if low<=code<=high and (not name or item['item_id']==name):
            values.append((code,item['item_id'],item['raw' if raw else 'engineering']['value']))
    return sorted(values)


def report_text(record,catalog,request,options):
    if record.get('schema')!='openbexi.spell.memory-image/1':return encoded(record)+'\n'
    values=selected(record,catalog,request.begin,request.end,raw=options.get('ValueFormat')=='Raw format')
    return ''.join(str(code)+'\t'+key+'\t'+encoded(value)+'\n' for code,key,value in values)


def case_proof(name,spec,row,project,catalog):
    assert row['passed'] is True and row['status']=='FINISHED' and row['states'][-1]['status']=='FINISHED'
    assert not any(key.endswith('_error') for key in row)
    assert row['dimension']==spec['dimension'] and row['source']==spec['source']==(project/'main.py').read_text(encoding='utf-8')
    assert encoded(row['result'])==encoded(read(project/'result.json'))==encoded({'completed':True})
    observed=read(project/'observed.json');assert observed==row['observed']
    assert all(encoded(v['actual'])==encoded(v['expected']) for v in observed['observations'])
    errors=[v for v in observed['calls'] if 'error_type' in v]
    assert len(errors)==ERRORS.get(name,0) and all(v['error_type']=='DriverException' for v in errors)
    for call in observed['calls']:
        if 'returned' in call:assert type(ast.literal_eval(call['returned'])).__name__==call['return_type']
    skipped=[v for v in observed['calls'] if v.get('policy')=='SKIP']
    assert len(skipped)==(1 if name in ('lookup:boundary','tmtc:boundary') else 0)
    assert all(v['returned']=='None' and v['return_type']=='NoneType' for v in skipped)
    assert sha(project/'native.log')==row['native_log_sha256'] and sha(project/'events.json')==row['events_sha256']
    log=(project/'native.log').read_text(encoding='utf-8')
    assert all(s not in log for s in ('AddressSanitizer:','runtime error:','Exception in thread'))
    assert not any(e.get('event')=='connectionError' or e.get('message',{}).get('id') in ('MSG_ERROR','MSG_PROMPT') for e in read(project/'events.json'))
    assert row['receipts']==[]
    controls=row['fixture_controls'];assert [c['command'] for c in controls]==[v['request'] for v in observed['fixtures']]
    step_cases={'packet-compare-range','compare:boundary','compare:recovery'}
    assert len(controls)==(1 if name in step_cases else 0)
    for control,saved in zip(controls,observed['fixtures']):
        command=control['command'];assert command==dict(action='step',token=command['token'])
        assert control['before']==row['initial_dss'] and control['after']==row['final_dss']
        assert control['before_packet_hex']==row['initial_packet_hex'] and control['after_packet_hex']==row['final_packet_hex']
        assert control['after']['epoch']==control['before']['epoch']
        assert control['after']['core']['tick']==control['before']['core']['tick']+1
        assert read(project/('fixture-'+command['token']+'.json'))==saved['response']
    if not controls:assert row['initial_dss']==row['final_dss'] and row['initial_packet_hex']==row['final_packet_hex']
    with evidence_database(project/'dss.sqlite') as db:
        assert db.execute('SELECT count(*) FROM operations').fetchone()[0]==0
        packets=[packet for packet, in db.execute('SELECT packet FROM packets')]
    assert bytes.fromhex(row['initial_packet_hex']) in packets and bytes.fromhex(row['final_packet_hex']) in packets
    final=row['final_ground'];initial=row['initial_ground']
    assert initial['images']==initial['reports']=={}
    assert {k:v for k,v in final.items() if k not in ('images','reports')}=={k:v for k,v in initial.items() if k not in ('images','reports')}
    for key,record in final['images'].items():
        if record.get('schema')=='openbexi.spell.memory-image/1':
            packet=bytes.fromhex(record['packet_hex']);assert packet in packets and hashlib.sha256(packet).hexdigest()==record['sha256']
            body=decode_tm(packet);assert body['satellite_epoch']==row['initial_dss']['epoch'] and body['database_revision']=='GENERIC-r1'
            expected_packet=row['final_packet_hex'] if key in ('after','second') and controls else row['initial_packet_hex']
            assert record['packet_hex']==expected_packet
        else:assert record['database_revision']=='GENERIC-r1' and record['epoch']==row['initial_dss']['epoch']
    telemetry={v['item_id']:v for v in catalog['telemetry']};commands={v['name']:v for v in catalog['commands']}
    effects=Counter();images=set();reports={};generated=[];comparisons=[];catalog_reads=0
    for call in row['rpc']:
        service,method=call['path'].split('/')[1:]
        descriptor=p.DESCRIPTOR.services_by_name[service.removeprefix('spell.driver.')].methods_by_name[method]
        request_bytes=bytes.fromhex(call['request']);request=GetMessageClass(descriptor.input_type).FromString(request_bytes)
        assert service.endswith(('_MEM','_TM','_EV'))
        if 'response' not in call:
            assert 'error' in call and not service.endswith('_EV');continue
        assert 'error' not in call
        response_bytes=bytes.fromhex(call['response']);response=GetMessageClass(descriptor.output_type).FromString(response_bytes)
        options=unpack(request.config) if hasattr(request,'config') and request.config.type_url else {}
        if method in ('RaiseEvent','CreateGoldenImage','GenerateReport'):
            effects[(hashlib.sha256(call['path'].encode()+b'\0'+request_bytes).hexdigest(),response_bytes)]+=1
        if method=='RaiseEvent':continue
        if method=='CreateGoldenImage':
            assert request.scp=='GENERIC' and set(options)<={'Type'} and response.value is True
            assert options.get('Type','JSON') in ('JSON','TM');images.add(request.filename)
        elif method=='GenerateReport':
            assert response.value is True and request.source in ('','GENERIC')
            text=report_text(final['images'][request.image],telemetry,request,options)
            key='memory-'+options['ReportId'] if 'ReportId' in options else request.image
            reports[key]=dict(image=request.image,content=text,sha256=hashlib.sha256(text.encode('ascii')).hexdigest()) if 'ReportId' in options else final['images'][request.image]
            generated.append(text)
        elif method=='MemoryLookup':
            actual=unpack(response)
            if request.report_type=='REPORT':expected=reports['memory-'+request.name]['content']
            else:
                record=final['images'][request.image]
                expected=record if record.get('schema')!='openbexi.spell.memory-image/1' else {
                    key:value for _,key,value in selected(record,telemetry,options.get('Begin',''),options.get('End',''),request.name,request.address,options.get('ValueFormat')=='Raw format')}
            assert encoded(actual)==encoded(expected)
        elif method=='CompareImages':
            comparisons.append(response.value)
            if name!='compare:recovery':
                # Both images are immutable for these cases; equality follows
                # from their independently decoded, selected binary values.
                a=final['images'][request.image1];b=final['images'][request.image2]
                expected=report_text(a,telemetry,request,options)==report_text(b,telemetry,request,options)
                assert response.value is expected
        elif method=='DatabaseLookup':
            assert request.source in ('','GENERIC') and request.type in ('TM','TC')
            query=request.name;lo,hi=0,0xffffffff
            if query.startswith('OPENBEXI_TMTC_LOOKUP_1:'):
                selection=json.loads(query.split(':',1)[1]);query=selection['Name']
                lo=int(selection['Begin'] or '0',0 if str(selection['Begin']).lower().startswith('0x') else 10)
                hi=int(selection['End'] or '4294967295',0 if str(selection['End']).lower().startswith('0x') else 10)
            table=telemetry if request.type=='TM' else commands;code='item_code' if request.type=='TM' else 'command_code'
            expected=(table[query] if lo<=table[query][code]<=hi else {}) if query else {k:v for k,v in table.items() if lo<=v[code]<=hi}
            if request.type=='TC' and query and expected:expected=dict(expected,kind='COMMAND')
            assert encoded(unpack(response.lookup))==encoded(expected);catalog_reads+=1
        else:raise AssertionError('Unexpected memory RPC: '+method)
    assert set(final['images'])==images and final['reports']==reports
    if name=='compare:recovery':assert comparisons==[True,False]
    files={q.name:q.read_bytes() for q in (project/'data/mem').iterdir() if q.is_file()}
    if name=='report:failure':assert files=={'preserved.txt':b'retained content'} and not generated
    elif generated:
        assert len(files)==1 and next(iter(files.values()))==generated[-1].encode('ascii')
    else:assert files=={}
    with evidence_database(project/'driver.sqlite') as db:
        grounds=[json.loads(v) for v, in db.execute('SELECT state FROM ground')]
        journal=db.execute('SELECT authority,digest,state,receipt FROM effects').fetchall()
    assert grounds==[final]
    actual=Counter()
    for authority,digest,state,receipt in journal:
        assert json.loads(authority)['definition']==name and state=='RECEIPTED';actual[(digest,receipt)]+=1
    assert actual==effects
    return dict(passed=True,dimension=row['dimension'],api_failures=len(errors),skipped=len(skipped),
        binary_images=sum(v.get('schema')=='openbexi.spell.memory-image/1' for v in final['images'].values()),
        generated_reports=len(generated),comparisons=comparisons,catalog_reads=catalog_reads,receipts=sum(actual.values()),
        oracle='Actual original-schema responses agree with retained binary packets, literal ASCII files, captured catalog definitions and exact durable receipts')


def review(path,overlay,telemetry,limits,revision,image,*,native_wheel=None,driver_wheel=None):
    raw=read(path);workspace=path.parent/'workspace'
    assert raw['passed'] is True and raw['controller_exit_code']==0 and raw['timed_out'] is False and raw['runtime_image']==image
    specs=frozen('conformance/memory_complete_cases.py',revision).CASES
    assert len(specs)==32 and set(raw['checks'])==set(specs)
    for name,digest in raw['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT,name,revision)).hexdigest()==digest and sha(path.parent/'inputs'/name)==digest
        if name.startswith('src/dss/'):assert sha(workspace/'fixture'/name.removeprefix('src/'))==digest
    assert raw['artifacts']=={q.relative_to(workspace).as_posix():sha(q) for q in workspace.rglob('*') if q.is_file()}
    assert read(workspace/'checks.json')==raw['checks'] and read(workspace/'runtime.json')==raw['runtime_sources']
    assert read(workspace/'host-inputs.json')==raw['host_inputs']
    for name in ('memory_native_cases.py','memory_complete_cases.py','memory_complete_controller.py','memory_features_provenance.py','installed_provenance.py'):
        assert sha(workspace/name)==raw['inputs']['conformance/'+name]
    wheels=None
    if raw['runtime_sources']['profile']=='fresh-composed-memory-wheel/1':
        assert overlay is telemetry is limits is None and native_wheel is not None and driver_wheel is not None
        from limit_telemetry_sources import verify
        wheels=verify(raw,native_wheel,driver_wheel,profile='fresh-composed-memory-wheel/1',required_recipes=('memory_feature_patches.py','memory_ranging_patches.py'))
    else:overlay_proof(raw,overlay,telemetry,limits,revision)
    catalog=read(workspace/'fixture/dss/data/satellite_database.json')
    checks={name:case_proof(name,specs[name],row,workspace/name.replace(':','__'),catalog) for name,row in raw['checks'].items()}
    return dict(passed=True,runtime_image=image,source_revision=revision,raw=ref(path),overlay=str(overlay.resolve()) if overlay else None,composed_wheels=wheels,
        telemetry_overlay=str(telemetry.resolve()) if telemetry else None,limit_overlay=str(limits.resolve()) if limits else None,checks=checks,
        review_source=ref(Path(__file__)),source_inputs=raw['inputs'],qualified_contracts=[],full_v05_accepted=False)
