"""Native probes for the manual's memory and TM/TC lookup operations."""
HEADER = '''##########
# NAME: Memory and database lookup baseline
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json,time
from pathlib import Path as FilePath
from spell.lang import functions as api
from spell.lang.constants import *
from spell.lang.modifiers import *
from spell.lib.exception import DriverException
observed={'calls':[],'observations':[],'fixtures':[]}
def save():FilePath('observed.json').write_text(json.dumps(observed,indent=2))
def call(name,*args,**options):
    row={'function':name,'args':repr(args),'options':repr(options)}
    observed['calls'].append(row);save()
    try:
        value=getattr(api,name)(*args,HandleError=False,PromptUser=False,**options)
        row.update(returned=repr(value),return_type=type(value).__name__);return value
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error));raise
    finally:save()
def equal(actual,expected):
    observed['observations'].append(dict(actual=actual,expected=expected));save()
    assert actual==expected,(actual,expected)
def rejects(operation):
    try:operation()
    except DriverException:pass
    else:raise AssertionError('Expected DriverException')
def fixture(action,**values):
    token=str(time.monotonic_ns());request=dict(token=token,action=action,**values)
    temporary=FilePath('fixture-request.tmp');temporary.write_text(json.dumps(request));temporary.replace('fixture-request.json')
    reply=FilePath('fixture-'+token+'.json');deadline=time.monotonic()+5
    while not reply.exists():
        assert time.monotonic()<deadline,'Fixture timeout';time.sleep(.01)
    result=json.loads(reply.read_bytes());assert 'error' not in result,result
    observed['fixtures'].append(dict(request=request,response=result));save();return result
def golden(image='reference',**options):equal(call('CreateGoldenImage','GENERIC',image,**options),True)
def lookup(image='reference',**options):
    return call('MemoryLookup',Image=image,Type='TM',Source='GENERIC',**options)
'''
CASES={}
def add(name,body,dimension='diagnostic'):
    CASES[name]=dict(dimension=dimension,source=HEADER+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n")

add('json-golden',"golden()")
add('json-compare',"""
golden()
equal(call('CompareMemoryImages',['reference','reference'],Type='JSON',Source='GENERIC',Begin='',End=''),True)
""")
add('json-lookup',"""
golden()
value=call('MemoryLookup',Name='DSS_STATE',Image='reference',Type='JSON',Source='GENERIC')
equal(value['database_revision'],'GENERIC-r1')
""")
add('json-report',"""
golden()
equal(call('GenerateMemoryReport',Image='reference',Type='JSON',Source='GENERIC',Begin='',End='',Destination='mem://state.txt'),True)
content=FilePath('data/mem/state.txt').read_text(encoding='ascii')
equal(json.loads(content)['database_revision'],'GENERIC-r1')
""")
add('compare-default-filters',"""
golden()
equal(call('CompareMemoryImages',Image=['reference','reference']),True)
""")
add('lookup-missing-recovery',"""
rejects(lambda:call('MemoryLookup',Name='DSS_STATE',Image='missing',Type='JSON',Source='GENERIC'))
golden()
value=call('MemoryLookup',Name='DSS_STATE',Image='reference',Type='JSON',Source='GENERIC')
equal(value['database_revision'],'GENERIC-r1')
""",'recovery')
add('tmtc-name',"""
value=call('TMTCLookup',Name='TM.POWER.BUS_VOLTAGE',Type='TM',Source='GENERIC')
equal(value['item_code'],1)
equal(value['item_id'],'TM.POWER.BUS_VOLTAGE')
""",'positive')
add('tmtc-command',"""
value=call('TMTCLookup','CMD1',Type='TC',Source='GENERIC')
equal(value['command_code'],2)
equal(value['effect'],'PAYLOAD_ON')
""",'positive')
add('tmtc-range',"""
equal(call('TMTCLookup',Name='TM.POWER.BUS_VOLTAGE',Type='TM',Source='GENERIC',Begin='2',End='3'),{})
value=call('TMTCLookup',Name='TM.POWER.BUS_VOLTAGE',Type='TM',Source='GENERIC',Begin='1',End='1')
equal(value['item_code'],1)
""",'boundary')
add('tmtc-range-failure',"""
rejects(lambda:call('TMTCLookup',Name='CMD1',Type='TC',Source='GENERIC',Begin='3',End='2'))
value=call('TMTCLookup',Name='CMD1',Type='TC',Source='GENERIC',Begin='2',End='2')
equal(value['command_code'],2)
""",'failure')
add('packet-raw-eng',"""
golden(Type='TM')
equal(lookup(Name='TM.POWER.BUS_VOLTAGE',ValueFormat=RAW),{'TM.POWER.BUS_VOLTAGE':28000})
equal(lookup(Name='TM.POWER.BUS_VOLTAGE',ValueFormat=ENG),{'TM.POWER.BUS_VOLTAGE':28.0})
""",'positive')
add('packet-address-boundary',"""
golden(Type='TM')
equal(lookup(Name='',Begin='1',End='1',ValueFormat=ENG),{'TM.POWER.BUS_VOLTAGE':28.0})
equal(lookup(Address=1,ValueFormat=RAW),{'TM.POWER.BUS_VOLTAGE':28000})
""",'boundary')
add('packet-compare-range',"""
golden('before',Type='TM')
fixture('step')
golden('after',Type='TM')
equal(call('CompareMemoryImages',Image=['before','after'],Type='TM',Source='GENERIC',Begin='1',End='1'),True)
equal(call('CompareMemoryImages',Image=['before','after'],Type='TM',Source='GENERIC',Begin='6',End='6'),False)
""")
add('packet-ascii-report',"""
golden(Type='TM')
equal(call('GenerateMemoryReport',Image='reference',Type='TM',Source='GENERIC',Begin='1',End='1',ValueFormat=RAW,Destination='mem://voltage.txt'),True)
content=FilePath('data/mem/voltage.txt').read_text(encoding='ascii')
equal(content,'1\\tTM.POWER.BUS_VOLTAGE\\t28000\\n')
""")
add('packet-range-failure',"""
golden(Type='TM')
rejects(lambda:lookup(Name='',Begin='3',End='2'))
rejects(lambda:lookup(Name='',Begin='invalid',End='2'))
equal(lookup(Name='',Begin='1',End='1'),{'TM.POWER.BUS_VOLTAGE':28.0})
""",'failure')
add('packet-missing-recovery',"""
rejects(lambda:lookup(image='missing',Name='TM.POWER.BUS_VOLTAGE'))
golden(Type='TM')
equal(lookup(Name='TM.POWER.BUS_VOLTAGE'),{'TM.POWER.BUS_VOLTAGE':28.0})
""",'recovery')
