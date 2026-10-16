"""LRM54-55: automatic analogue/status limits and the complete Send example."""
from memory_native_cases import HEADER

HEADER=HEADER.replace("value=getattr(api,name)(*args,HandleError=False,PromptUser=False,**options)",
    "options.setdefault('HandleError',False);options.setdefault('PromptUser',False)\n        value=getattr(api,name)(*args,**options)")
SUPPORT='''
import sqlite3
from contextlib import closing
from spell.lib.exception import SyntaxException
from spell.lib.adapter.utctime import SECOND
VOLTAGE='TM.POWER.BUS_VOLTAGE'
MODE='TM.CORE.MODE'

def ground():
    with closing(sqlite3.connect('driver.sqlite')) as db:
        return json.loads(db.execute('SELECT state FROM ground').fetchone()[0])

def thresholds(low,high):return {LoRed:low,LoYel:low,HiYel:high,HiRed:high}
def seed(name=VOLTAGE):
    definition=thresholds(20,40) if name==VOLTAGE else {Nominal:['NOMINAL'],Error:['FAULT']}
    equal(call('SetLimits',name,Definition=definition),True)

def values(name=VOLTAGE):return call('GetLimits',name,Select='GENERIC')
def exact_limits(low,high):
    row=values()
    equal({key:row[key] for key in (LoRed,LoYel,HiYel,HiRed)},thresholds(low,high))

def send_adjust(target=28,**config):
    return call('Send',command='CMD1',verify=[[VOLTAGE,eq,target]],Confirm=False,Wait=False,
                Timeout=2,Retries=0,AdjLimits=True,Tolerance=.5,**config)

def complex_send(arg2=255,delay=10*SECOND,**config):
    config.setdefault('PromptFailure',False)
    return call('Send',command='CMDNAME',args=[['ARG1',1.0],['ARG2',arg2,{Radix:HEX}]],
        verify=[[VOLTAGE,eq,28.0,{Tolerance:.1}],['TM.CORE.TICK',gt,0,{Timeout:20}]],
        Delay=delay,Tolerance=.5,Confirm=False,Wait=False,Retries=0,**config)

fixture('feed',enabled=True)
'''
CASES={}


def add(feature,dimension,body):
    source=HEADER+SUPPORT+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n"
    compile(source,feature+':'+dimension,'exec')
    CASES[feature+':'+dimension]=dict(feature=feature,dimension=dimension,source=source)


add('adjust-analog','positive','''
seed();equal(send_adjust(),True);exact_limits(27.5,28.5)
''')
add('adjust-analog','boundary','''
seed()
equal(call('Send',command='CMD1',verify=[[VOLTAGE,eq,28,{Tolerance:0}]],Confirm=False,
    Wait=False,Timeout=2,Retries=0,AdjLimits=True,Tolerance=.5),True)
exact_limits(28,28)
''')
add('adjust-analog','failure','''
seed();before=ground()
rejects(lambda:call('Send',command='CMD1',verify=[['MISSING',eq,28]],Confirm=False,
    Wait=False,Timeout=2,Retries=0,AdjLimits=True))
equal(ground(),before)
''')
add('adjust-analog','recovery','''
seed();before=ground()
rejects(lambda:call('Send',command='MISSING',verify=[[VOLTAGE,eq,28]],Confirm=False,AdjLimits=True))
equal(ground(),before);equal(send_adjust(),True);exact_limits(27.5,28.5)
''')
add('adjust-status','positive','''
seed(MODE)
equal(call('Send',command='TC.SIMULATOR.SET_MODE',args=[['MODE','SAFE']],
    verify=[[MODE,eq,'SAFE']],Confirm=False,Wait=False,Timeout=2,Retries=0,AdjLimits=True),True)
row=values(MODE);equal(row[Nominal],['SAFE']);assert 'SAFE' not in row.get(Error,[])
''')
add('adjust-status','boundary','''
seed(MODE);before=values(MODE)
equal(call('Send',command='CMD1',verify=[[MODE,eq,'NOMINAL',{AdjLimits:False}]],
    Confirm=False,Wait=False,Timeout=2,Retries=0,AdjLimits=True),True)
equal(values(MODE),before)
''')
add('adjust-status','failure','''
seed(MODE);before=ground()
rejects(lambda:call('Send',command='CMD1',verify=[['MISSING',eq,'SAFE']],
    Confirm=False,Wait=False,Timeout=2,Retries=0,AdjLimits=True))
equal(ground(),before)
''')
add('adjust-status','recovery','''
seed(MODE)
equal(call('Send',command='CMD1',verify=[[MODE,eq,'MISSING']],Confirm=False,Wait=False,
    Timeout=2,Retries=0,AdjLimits=True,OnFalse=NOACTION),False)
equal(call('Send',command='CMD2',verify=[[MODE,eq,'NOMINAL']],Confirm=False,Wait=False,
    Timeout=2,Retries=0,AdjLimits=True),True)
equal(values(MODE)[Nominal],['NOMINAL'])
''')
add('complex-send','positive','''
before=ground();began=time.monotonic()
equal(complex_send(HandleError=True,OnFailure=CANCEL),True)
elapsed=time.monotonic()-began;assert elapsed>=10
observed['observations'].append(dict(send_elapsed=elapsed));save()
equal(ground(),before)
''')
add('complex-send','boundary','''
equal(complex_send(arg2=0,delay=0,HandleError=True,OnFailure=CANCEL),True)
''')
add('complex-send','failure','''
before=ground()
equal(complex_send(arg2=-1,delay=0,HandleError=True,OnFailure=CANCEL),False)
equal(ground(),before)
''')
add('complex-send','recovery','''
equal(complex_send(arg2=-1,delay=0,HandleError=True,OnFailure=CANCEL),False)
equal(complex_send(arg2=255,delay=0,HandleError=True,OnFailure=CANCEL),True)
''')
