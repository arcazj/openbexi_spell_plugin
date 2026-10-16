"""Retained native probes for the remaining complete telemetry surface."""
HEADER = '''##########
# NAME: Remaining telemetry surface
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json,time
from pathlib import Path as FilePath
from spell.lang import functions as api
from spell.lang.constants import *
from spell.lang.modifiers import *
from spell.lib.adapter.utctime import MINUTE
from spell.lib.exception import DriverException
observed={'calls':[],'observations':[],'fixtures':[]}
def save():FilePath('observed.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
def fixture(action,**values):
    token=str(time.monotonic_ns())
    request=dict(token=token,action=action,**values)
    temporary=FilePath('fixture-request.tmp');temporary.write_text(json.dumps(request))
    temporary.replace('fixture-request.json')
    reply=FilePath('fixture-'+token+'.json');deadline=time.monotonic()+5
    while not reply.exists():
        assert time.monotonic()<deadline,'Fixture timeout'
        time.sleep(.01)
    result=json.loads(reply.read_bytes());assert 'error' not in result,result
    observed['fixtures'].append({'request':request,'response':result});save()
    return result
def call(name,*args,**options):
    row={'function':name,'args':repr(args),'options':repr(options)}
    observed['calls'].append(row);started=time.monotonic()
    try:
        result=getattr(api,name)(*args,HandleError=False,PromptUser=False,**options)
        row.update(returned=repr(result),return_type=type(result).__name__)
        return result
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error));raise
    finally:row['seconds']=time.monotonic()-started;save()
def equal(actual,expected):
    observed['observations'].append({'actual':actual,'expected':expected});save()
    assert actual==expected,(actual,expected)
def rejects(function):
    try:function()
    except DriverException:pass
    else:raise AssertionError('Expected DriverException')
'''
CASES = {}


def add(name, body, **options):
    CASES[name] = dict(source=HEADER+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n",
        dimension='diagnostic', **options)


add('good-source', '''
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False),28.0)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False,ValueFormat=RAW),28000)
''')
for label, faults in (
    ('quality-bad', {'telemetry_quality': 'BAD'}),
    ('quality-suspect', {'telemetry_quality': 'SUSPECT'}),
    ('quality-unknown', {'telemetry_quality': 'UNKNOWN'}),
    ('invalid', {'telemetry_validity': 'INVALID'}),
    ('stale', {'stale': True}),
    ('missing-item', {'missing_items': ['TM.POWER.BUS_VOLTAGE']}),
):
    add(label, '''
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False))
fixture('reset',faults={})
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False),28.0)
''', faults=faults)
add('link-outage', '''
fixture('link',enabled=False)
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False))
fixture('link',enabled=True)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=False),28.0)
''')
add('minute-timeout', '''
fixture('feed',enabled=True)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=1*MINUTE),28.0)
''')
add('timeout-recovery', '''
fixture('feed',enabled=False)
rejects(lambda:call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=.1))
fixture('feed',enabled=True)
equal(call('GetTM','TM.POWER.BUS_VOLTAGE',Wait=True,Timeout=2),28.0)
''')
add('printed-result', '''
result=call('Verify',[['TM.POWER.BUS_VOLTAGE',eq,28.0],['TM.THERMAL.MODE',eq,'wrong']],
            Wait=False,Retries=0,OnFalse=NOACTION)
assert not result
equal(result.keys(),['0: TM.POWER.BUS_VOLTAGE','1: TM.THERMAL.MODE'])
for name in result.keys():
    line=name+' : '+str(result[name])
    api.Display(line)
    observed['observations'].append({'displayed':line});save()
''')
add('list-between', '''
for operator,wanted in [(bw,True),(nbw,False)]:
    result=call('Verify',['TM.POWER.BUS_VOLTAGE',operator,28.0,28.0],
                Wait=False,Retries=0,Tolerance=0,OnFalse=NOACTION)
    equal(bool(result),wanted)
''')
