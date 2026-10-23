"""Reference images through the original RPC schema, real DSS and SQLite."""
import hashlib
import json
import types
import ast

import pytest
from google.protobuf.message_factory import GetMessageClass

import test_command_rpc as base
import memory_feature_patches
import limit_feature_patches
import telemetry_feature_patches
from openbexi_spell_dss.codec import pack,unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from openbexi_spell_dss.memory_images import LOOKUP_PREFIX


def composed(name):
    path='openbexi_spell_dss/'+name+'.py'
    raw=(base.ROOT/'driver_plugin/src'/path).read_bytes()
    recipes=base.integrated_patches.DRIVER_RECIPES
    memory=() if any(recipe.__name__=='memory_ranging_patches' for recipe in recipes) else (memory_feature_patches,)
    for recipe in dict.fromkeys((*recipes,limit_feature_patches,telemetry_feature_patches,*memory)):
        if path in recipe.PREIMAGES:raw=recipe.apply(path,raw)
    module=types.ModuleType('openbexi_spell_dss._memory_test_'+name)
    module.__package__ = 'openbexi_spell_dss'
    exec(compile(raw,path,'exec'),module.__dict__)
    return module


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setattr(base,'composed',composed)
    yield from base.bridge.__wrapped__(tmp_path,monkeypatch)


def rpc(env,method,request,family='MEM'):
    descriptor=p.DESCRIPTOR.services_by_name['SPELLDriverInterface_'+family].methods_by_name[method]
    raw=env.dispatch('/spell.driver.SPELLDriverInterface_'+family+'/'+method,request.SerializeToString())
    return GetMessageClass(descriptor.output_type).FromString(raw)


def capture(env,name='reference',rtype='TM'):
    assert rpc(env,'CreateGoldenImage',p.GoldenImageRequest(scp='GENERIC',filename=name,config=pack({'Type':rtype}))).value


def lookup(env,image='reference',name='',address='',**config):
    return unpack(rpc(env,'MemoryLookup',p.MemoryLookupRequest(name=name,address=address,image=image,
        report_type='TM',source='GENERIC',config=pack(config))))


def test_image_is_retained_binary_and_values_do_not_follow_later_ticks(env):
    capture(env)
    saved=env.dispatcher.ground.state()['images']['reference']
    assert saved['packet_hex']==env.engine.telemetry()['packet_hex']
    assert saved['sha256']==hashlib.sha256(bytes.fromhex(saved['packet_hex'])).hexdigest()
    assert lookup(env,name='TM.POWER.BUS_VOLTAGE',ValueFormat='Raw format')=={'TM.POWER.BUS_VOLTAGE':28000}
    assert lookup(env,name='TM.POWER.BUS_VOLTAGE')=={'TM.POWER.BUS_VOLTAGE':28.0}
    before=lookup(env,name='TM.CORE.TICK')
    base.step(env,3)
    assert lookup(env,name='TM.CORE.TICK')==before
    capture(env,'later')
    assert lookup(env,image='later',name='TM.CORE.TICK')!=before


def test_ranges_and_address_boundaries_are_applied_to_captured_image(env):
    capture(env)
    assert lookup(env,Begin='0x1',End='1')=={'TM.POWER.BUS_VOLTAGE':28.0}
    assert lookup(env,address='1',ValueFormat='Raw format')=={'TM.POWER.BUS_VOLTAGE':28000}
    for settings in ({'Begin':'2','End':'1'},{'Begin':True},{'End':'no'},{'Begin':-1}):
        with pytest.raises(ValueError):lookup(env,**settings)
    with pytest.raises(ValueError,match='Unknown reference memory address'):lookup(env,address='999')
    assert len(lookup(env,Begin='1',End='2'))==2


def test_comparison_filters_ignore_unselected_changed_data(env):
    capture(env,'before');base.step(env,1);capture(env,'after')
    def compare(begin,end):
        return rpc(env,'CompareImages',p.CompareMemoryReportRequest(image1='before',image2='after',
            report_type='TM',source='GENERIC',begin=begin,end=end)).value
    assert compare('1','1') is True
    assert compare('6','6') is False
    assert compare('','') is False


def test_ascii_report_is_retained_and_original_rpc_returns_its_exact_content(env):
    capture(env)
    assert rpc(env,'GenerateReport',p.MemoryReportRequest(image='reference',report_type='TM',
        source='GENERIC',begin='1',end='1',config=pack({'ReportId':'report1','ValueFormat':'Raw format'}))).value
    text=unpack(rpc(env,'MemoryLookup',p.MemoryLookupRequest(name='report1',image='reference',report_type='REPORT',source='GENERIC')))
    assert text=='1\tTM.POWER.BUS_VOLTAGE\t28000\n'
    row=env.dispatcher.ground.state()['reports']['memory-report1']
    assert row==dict(image='reference',content=text,sha256=hashlib.sha256(text.encode('ascii')).hexdigest())
    assert env.journal.db.execute('SELECT state FROM effects').fetchall()==[('RECEIPTED',),('RECEIPTED',)]
    base.step(env,1)
    assert unpack(rpc(env,'MemoryLookup',p.MemoryLookupRequest(name='report1',image='reference',report_type='REPORT')))==text


def test_invalid_report_and_revoked_authority_do_not_write_effect_intents(env):
    capture(env)
    before=env.dispatcher.ground.state()
    count=env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]
    for request in (p.MemoryReportRequest(image='missing'),
                    p.MemoryReportRequest(image='reference',report_type='TM',begin='9',end='2'),
                    p.MemoryReportRequest(image='reference',report_type='TM',config=pack({'ReportId':'../escape'}))):
        with pytest.raises(ValueError):rpc(env,'GenerateReport',request)
    env.allowed=False
    with pytest.raises(PermissionError):capture(env,'denied')
    assert env.dispatcher.ground.state()==before
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==count
    env.allowed=True;capture(env,'recovered')


def test_json_profile_remains_compatible_and_missing_images_recover(env):
    with pytest.raises(ValueError):lookup(env,image='missing')
    capture(env,rtype='JSON')
    expected=env.transport.get('state')  # Ground snapshots include HTTP transport metadata.
    assert unpack(rpc(env,'MemoryLookup',p.MemoryLookupRequest(name='DSS_STATE',image='reference')))==expected
    assert rpc(env,'CompareImages',p.CompareMemoryReportRequest(image1='reference',image2='reference')).value
    assert rpc(env,'GenerateReport',p.MemoryReportRequest(image='reference')).value
    assert env.dispatcher.ground.state()['reports']['reference']==expected


def test_database_queries_apply_catalog_code_bounds_and_recover(env):
    def query(name,kind,begin='',end=''):
        encoded=LOOKUP_PREFIX+json.dumps(dict(Name=name,Begin=begin,End=end))
        return unpack(rpc(env,'DatabaseLookup',p.LookupRequest(name=encoded,type=kind,source='GENERIC'),'TM').lookup)
    assert query('TM.POWER.BUS_VOLTAGE','TM','1','1')['item_code']==1
    assert query('TM.POWER.BUS_VOLTAGE','TM','2','3')=={}
    assert set(query('','TM','1','2'))=={'TM.POWER.BUS_VOLTAGE','TM.POWER.SAFE_MODE'}
    assert query('CMD1','TC','2','2')['effect']=='PAYLOAD_ON'
    assert list(query('','TC','2','2'))==['CMD1']
    with pytest.raises(ValueError):query('CMD1','TC','3','2')
    assert query('CMD1','TC')['command_code']==2
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0


def test_sequence_catalog_and_address_queries_keep_distinct_semantics(env):
    request=p.LookupRequest(name='SEQ.DUPLICATE',type='TC',source='GENERIC')
    def read(request):return unpack(rpc(env,'DatabaseLookup',request,'TM').lookup)
    sequence=read(request)
    assert sequence['kind']=='SEQUENCE' and sequence['name']=='SEQ.DUPLICATE'
    assert [member['command'] for member in sequence['members']]==['CMD1','CMD1','CMD2']
    assert 'command_code' not in sequence
    bounded=p.LookupRequest(name=LOOKUP_PREFIX+json.dumps(dict(Name='SEQ.DUPLICATE',Begin='',End='')),
        type='TC',source='GENERIC')
    with pytest.raises(ValueError,match='concrete TM/TC entry'):read(bounded)
    with pytest.raises(ValueError):read(p.LookupRequest(name='MISSING',type='TC',source='GENERIC'))
    env.allowed=False
    with pytest.raises(PermissionError):read(request)
    env.allowed=True
    assert read(request)==sequence
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0


def proxy(env):
    # Exercise the unmodified proxy function bodies against the actual original
    # protobuf dispatcher. Native import/runtime validation is a separate gate.
    path=base.ROOT/'driver_plugin/src/openbexi_dss_proxy/memory_support.py'
    source=ast.parse(path.read_bytes())
    source.body=[node for node in source.body if not (isinstance(node,ast.ImportFrom) and
        (node.module.startswith('spell.') or node.level))]
    common=ast.parse((base.ROOT/'driver_plugin/src/openbexi_dss_proxy/common.py').read_bytes())
    policy=next(ast.literal_eval(node.value) for node in common.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id=='POLICY' for target in node.targets))
    module=types.ModuleType('_memory_proxy_functions')
    module.__dict__.update(DriverException=RuntimeError,p=p,PackValue=pack,UnpackValue=unpack,POLICY=policy,
                          call=lambda family,method,request:rpc(env,method,request,family))
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module


def context(root):
    return types.SimpleNamespace(getLocationType=lambda scheme:'file' if scheme=='mem' else '',
        getLocationPath=lambda scheme:str(root),getLocationExt=lambda scheme:'')


@pytest.mark.parametrize('interruptible',[False,True])
def test_proxy_embedded_fields_and_integer_addresses_cross_original_rpc(env,interruptible):
    module=proxy(env)
    assert module.capture('GENERIC','snapshot',{'AllowInterrupt':interruptible,'Source':'GENERIC','Name':'snapshot','Type':'TM'})
    assert module.lookup(None,1,'snapshot','TM','GENERIC',{'AllowInterrupt':interruptible,'Image':'snapshot','Address':1,'Type':'TM','Source':'GENERIC','ValueFormat':'Raw format'})=={'TM.POWER.BUS_VOLTAGE':28000}
    assert module.database('CMD1','TC','GENERIC',{'AllowInterrupt':interruptible,'Name':'CMD1','Type':'TC','Source':'GENERIC','Begin':'3','End':'4'})=={}


def test_original_tm_adapter_defaults_allow_exact_and_bounded_catalog_queries(env):
    module=proxy(env)
    # These are the original TmInterface.INTERFACE_DEFAULTS, in addition to the
    # helper-owned options exercised above. The native suite tests their actual
    # merge by the original adapter, without replacing the helper or its config.
    config={'Timeout':15,'Retries':2,'Tolerance':0,'RelTolerance':1e-9,
            'Wait':False,'IgnoreCase':False,'ValueFormat':'Eng format',
            'AllowInterrupt':False,'Notify':True,'HandleError':False,'PromptUser':False}
    assert module.database('TM.POWER.BUS_VOLTAGE','TM','GENERIC',config)['item_code']==1
    assert module.database('CMD1','TC','GENERIC',dict(config,Begin='3',End='4'))=={}
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0


def test_original_language_xml_interface_defaults_are_not_query_filters(env):
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(base.ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        document=ET.fromstring(archive.read('config/spell/language.xml'))
    fields={node.attrib['name']:node.text for node in document.find("defaults[@interface='TM']")}
    defaults={key:ast.literal_eval(fields[key]) for key in
              ('Timeout','Retries','Tolerance','Wait','Delay','IgnoreCase','AdjLimits')}
    assert defaults['Timeout']==30 and defaults['Tolerance']==.1
    module=proxy(env)
    assert module.database('CMD1','TC','GENERIC',defaults,defaults)['command_code']==2
    for key,value in [('Timeout',31),('Tolerance',.2),('Delay',1),('AdjLimits',True)]:
        with pytest.raises(RuntimeError,match='Unsupported database query modifier: '+key):
            module.database('CMD1','TC','GENERIC',dict(defaults,**{key:value}),defaults)
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0


@pytest.mark.parametrize('key,value',[
    ('Timeout',30),('Retries',3),('Tolerance',1),('RelTolerance',.1),
    ('Wait',True),('IgnoreCase',True),('Wait',0),('Unknown',True),
])
def test_catalog_rejects_nondefault_acquisition_or_unknown_options(env,key,value):
    module=proxy(env);calls=[]
    module.call=lambda *args:calls.append(args)
    with pytest.raises(RuntimeError,match='Unsupported database query modifier'):
        module.database('CMD1','TC','GENERIC',{key:value})
    assert calls==[]


def test_proxy_writes_ascii_atomically_and_preserves_existing_file_on_rpc_failure(env,tmp_path):
    capture(env)
    module=proxy(env);root=tmp_path/'reports';root.mkdir()
    target=root/'voltage.txt';target.write_text('previous')
    owner=types.SimpleNamespace(getContextConfig=lambda:context(root))
    options=dict(Destination='mem://voltage.txt',ValueFormat='Raw format',Image='reference',Type='TM',Source='GENERIC',Begin='1',End='1')
    assert module.generate(owner,'reference','TM','1','1','GENERIC',options)
    assert target.read_bytes()==b'1\tTM.POWER.BUS_VOLTAGE\t28000\n'
    before=target.read_bytes()
    with pytest.raises(RuntimeError):module.generate(owner,'missing','TM','1','1','GENERIC',options)
    assert target.read_bytes()==before
    assert sorted(p.name for p in root.iterdir())==['voltage.txt']


def test_proxy_rejects_destination_escape_before_any_remote_effect(env,tmp_path):
    module=proxy(env);owner=types.SimpleNamespace(getContextConfig=lambda:context(tmp_path))
    for uri in ('mem://../escape','mem:///absolute','mem://a/../../escape','unknown://report','mem://C:/file'):
        with pytest.raises(RuntimeError):module.generate(owner,'reference','TM','','','GENERIC',{'Destination':uri})
    assert env.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
