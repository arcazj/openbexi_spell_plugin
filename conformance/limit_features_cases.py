"""Independent native limit scenarios; each assertion observes real API/storage."""
HEADER = '''##########
# NAME: Full limit behavior
# SPACECRAFT: GENERIC
# PYTHON VERSION: 3
##########
import json,sqlite3
from contextlib import closing
from pathlib import Path as FilePath
from spell.lang import functions as api
from spell.lang.constants import *
from spell.lang.modifiers import *
from spell.lib.exception import DriverException,SyntaxException
observed={'calls':[],'observations':[]}
def save():FilePath('observed.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
def call(name,*args,**options):
    row={'function':name,'args':repr(args),'options':repr(options)}
    observed['calls'].append(row)
    try:
        result=getattr(api,name)(*args,HandleError=False,PromptUser=False,**options)
        row.update(returned=result,return_type=type(result).__name__)
        return result
    except Exception as error:
        row.update(error_type=type(error).__name__,error=str(error))
        raise
    finally:save()
def equal(actual,expected):
    observed['observations'].append({'actual':actual,'expected':expected});save()
    assert actual==expected,(actual,expected)
def ground():
    with closing(sqlite3.connect('driver.sqlite')) as db:
        return json.loads(db.execute('SELECT state FROM ground').fetchone()[0])
def snapshot():
    with closing(sqlite3.connect('driver.sqlite')) as db:
        rows=db.execute('SELECT * FROM effects ORDER BY request_id').fetchall()
        return ground(),[[{'binary_hex':value.hex()} if type(value) is bytes else value for value in row] for row in rows]
def unchanged(function,error=DriverException):
    before=snapshot()
    try:function()
    except error:pass
    else:raise AssertionError('Expected failure')
    equal(snapshot(),before)
HARD={LoRed:10,LoYel:20,HiYel:30,HiRed:40}
def seed(**metadata):
    assert call('SetLimits','TMparam',Definition=dict(HARD,**metadata))
def inject(value,name='TMparam'):
    assert call('SetGroundParameter',name,value)
def definition(name='TMparam',key='GENERIC'):
    return call('GetLimits',name,Select=key)
def alarm(value,name='TMparam'):
    inject(value,name)
    return call('IsAlarmed',name)
'''
CASES = {}


def add(feature, dimension, body):
    CASES[feature+':'+dimension] = dict(feature=feature, dimension=dimension,
        source=HEADER+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n")


add('named', 'positive', '''
values={'ID1':dict(HARD,Active=True),'ID2':dict(HARD,Active=False)}
assert call('SetLimits','TMparam',Limits=values)
equal(sorted(call('GetLimits','TMparam',Select=ALL)),sorted(values))
equal(list(call('GetLimits','TMparam',Select=ACTIVE)),['ID1'])
assert call('SetLimits','TMparam',Definition={LoYel:19},Select='ID1')
equal(definition(key='ID1')[LoYel],19)
equal(definition(key='ID2')[LoYel],20)
''')
add('named', 'boundary', '''
assert call('SetLimits','TMparam',Limits={'ID'+str(n):dict(HARD) for n in range(16)})
equal(len(call('GetLimits','TMparam',Select=ALL)),16)
unchanged(lambda:call('SetLimits','TMparam',Limits={'EXTRA':dict(HARD)}))
''')
add('named', 'failure', '''
seed()
unchanged(lambda:call('SetLimits','TMparam',Limits={'GENERIC':{LoYel:19},'OTHER':{LoRed:1}}))
unchanged(lambda:call('GetLimits','TMparam',Select='ABSENT'))
equal(definition()[LoYel],20)
''')
add('named', 'recovery', '''
seed()
unchanged(lambda:call('SetLimits','TMparam',Select='ABSENT',LoRed=9))
assert call('SetLimits','TMparam',Definition={Active:False},Select='GENERIC')
equal(call('GetLimits','TMparam',Select=ACTIVE),{})
assert call('SetLimits','TMparam',Definition={Active:True},Select='GENERIC')
equal(list(call('GetLimits','TMparam',Select=ACTIVE)),['GENERIC'])
''')

add('metadata', 'positive', '''
label="Definition, '"+chr(0x3b1)+"'"
seed(Name=label,Hysteresis=2,Algorithm='TMparam1<TMparam2+TMparam3')
row=definition()
equal(row[Name],label);equal(row[Hysteresis],2)
equal(row[Algorithm],'TMparam1<TMparam2+TMparam3');equal(row[Type],HARDSOFT)
''')
add('metadata', 'boundary', '''
seed(Name='x'*256,Hysteresis=1024,Algorithm='')
equal(call('GetLimits','TMparam',Select='GENERIC',Value=Hysteresis),1024)
unchanged(lambda:call('SetLimits','TMparam',Definition={Name:'x'*257}))
unchanged(lambda:call('SetLimits','TMparam',Definition={Hysteresis:1025}))
''')
add('metadata', 'failure', '''
seed()
for value in (True,-1,1.5):
    unchanged(lambda:call('SetLimits','TMparam',Definition={Hysteresis:value}))
unchanged(lambda:call('SetLimits','TMparam',Definition={Active:'yes'}))
''')
add('metadata', 'recovery', '''
seed(Name='before')
unchanged(lambda:call('SetLimits','TMparam',Definition={Name:123}))
assert call('SetLimits','TMparam',Definition={Name:'after',Hysteresis:0})
equal(definition()[Name],'after');equal(definition()[LoYel],20)
''')

add('activation', 'positive', '''
inject(1,'TMparam1');inject(2,'TMparam2');inject(2,'TMparam3')
seed(Algorithm='TMparam1<TMparam2+TMparam3')
equal(list(call('GetLimits','TMparam',Select=ACTIVE)),['GENERIC'])
inject(5,'TMparam1')
equal(call('GetLimits','TMparam',Select=ACTIVE),{})
equal(alarm(50),False)
''')
add('activation', 'boundary', '''
inject(4,'TMparam1');inject(2,'TMparam2');inject(2,'TMparam3')
seed(Algorithm='TMparam1<TMparam2+TMparam3')
equal(call('GetLimits','TMparam',Select=ACTIVE),{})
assert call('SetLimits','TMparam',Definition={Algorithm:'TMparam1<=TMparam2+TMparam3'},Select='GENERIC')
equal(len(call('GetLimits','TMparam',Select=ACTIVE)),1)
''')
add('activation', 'failure', '''
seed()
for expression in ('UNKNOWN>0','open("x")','TMparam**10000>0'):
    unchanged(lambda:call('SetLimits','TMparam',Definition={Algorithm:expression}))
''')
add('activation', 'recovery', '''
seed(Algorithm='1/0>0')
unchanged(lambda:call('GetLimits','TMparam',Select=ACTIVE))
assert call('SetLimits','TMparam',Definition={Algorithm:''},Select='GENERIC')
equal(alarm(50),True)
''')

STATUS_SEED = "assert call('SetLimits','TM.CORE.MODE',Type=STATUS,Definition={Nominal:['NOMINAL'],Warning:['SAFE'],Error:['FAILED'],Ignore:['OFF']})\n"
add('status', 'positive', STATUS_SEED+'''
for state,wanted in [('NOMINAL',False),('SAFE',True),('FAILED',True),('OFF',False)]:
    equal(alarm(state,'TM.CORE.MODE'),wanted)
equal(definition('TM.CORE.MODE')[Ignore],['OFF'])
''')
add('status', 'boundary', '''
value="A,'B' "+chr(0x3b1)
assert call('SetLimits','TM.CORE.MODE',Definition={Nominal:[value]})
equal(call('GetLimits','TM.CORE.MODE',Select='GENERIC',Value=Nominal),[value])
equal(definition('TM.CORE.MODE')[Warning],[])
equal(alarm(value,'TM.CORE.MODE'),False)
equal(alarm('UNLISTED','TM.CORE.MODE'),True)
''')
add('status', 'failure', STATUS_SEED+'''
unchanged(lambda:call('SetLimits','TM.CORE.MODE',Definition={Nominal:['SAFE']}))
unchanged(lambda:call('SetLimits','TM.CORE.MODE',Definition={Nominal:[123]}))
''')
add('status', 'recovery', STATUS_SEED+'''
equal(alarm('FAILED','TM.CORE.MODE'),True)
assert call('SetLimits','TM.CORE.MODE',Nominal=['NOMINAL','RECOVERED'],Select='GENERIC')
equal(alarm('RECOVERED','TM.CORE.MODE'),False)
equal(definition('TM.CORE.MODE')[Nominal],['NOMINAL','RECOVERED'])
''')

for feature, kind, delta, bad, values in (
    ('step', 'STEP', '[2,3]', '[-1,3]', [(10,False),(13,False),(17,True),(15,False),(12,True)]),
    ('spike', 'SPIKE', '3', '-1', [(10,False),(13,False),(17,True),(14,False),(10,True)]),
):
    start="assert call('SetLimits','TMparam',Type="+kind+",Definition={Delta:"+delta+"})\n"
    add(feature, 'positive', start+"for value,wanted in "+repr(values)+":\n    equal(alarm(value),wanted)\n")
    zero = '[0,0]' if feature == 'step' else '0'
    add(feature, 'boundary', start+"assert call('SetLimits','TMparam',Delta="+zero+")\nequal(alarm(10),False)\nequal(alarm(10),False)\nequal(alarm(10.001),True)\n")
    add(feature, 'failure', start+"unchanged(lambda:call('SetLimits','TMparam',Delta="+bad+"))\nequal(call('GetLimits','TMparam',Select='GENERIC',Value=Delta),"+delta+")\n")
    add(feature, 'recovery', start+"equal(alarm(10),False)\nequal(alarm(20),True)\nequal(alarm(20),False)\nequal(definition()[Type],"+kind+")\n")

add('hysteresis', 'positive', '''
seed(Hysteresis=2)
equal(alarm(50),False)
equal(call('IsAlarmed','TMparam'),False)
equal(alarm(50),True)
equal(ground()['limit_history']['TMparam']['GENERIC']['violations'],2)
''')
add('hysteresis', 'boundary', '''
seed(Hysteresis=0);equal(alarm(50),True)
assert call('SetLimits','TMparam',Definition={Hysteresis:1})
equal(alarm(50),True)
equal(alarm(20),False);equal(alarm(30),False)
''')
add('hysteresis', 'failure', '''
seed(Hysteresis=2);equal(alarm(50),False)
unchanged(lambda:call('SetLimits','TMparam',Definition={Hysteresis:-1}))
equal(call('IsAlarmed','TMparam'),False)
equal(alarm(50),True)
''')
add('hysteresis', 'recovery', '''
seed(Hysteresis=2);equal(alarm(50),False);equal(alarm(50),True)
equal(alarm(25),False)
equal(alarm(50),False);equal(alarm(50),True)
''')

add('alarm-control', 'positive', '''
seed();equal(alarm(50),True)
assert call('DisableAlarm','TMparam');equal(call('IsAlarmed','TMparam'),False)
equal(ground()['limit_enabled']['TMparam'],False)
assert call('EnableAlarm','TMparam');equal(call('IsAlarmed','TMparam'),True)
equal(ground()['limit_enabled']['TMparam'],True)
''')
add('alarm-control', 'boundary', '''
assert call('DisableAlarm','TMparam');assert call('DisableAlarm','TMparam')
equal(call('IsAlarmed','TMparam'),False)
assert call('EnableAlarm','TMparam');assert call('EnableAlarm','TMparam')
equal(call('IsAlarmed','TMparam'),False)
''')
add('alarm-control', 'failure', '''
seed()
unchanged(lambda:call('DisableAlarm','ABSENT'))
unchanged(lambda:call('EnableAlarm','TMparam','extra'),SyntaxException)
unchanged(lambda:call('DisableAlarm','TMparam',Unknown=True))
''')
add('alarm-control', 'recovery', '''
seed(Hysteresis=2);equal(alarm(50),False);equal(alarm(50),True)
assert call('DisableAlarm','TMparam');assert call('EnableAlarm','TMparam')
equal(call('IsAlarmed','TMparam'),False)
equal(alarm(50),True)
''')

add('adjust-analog', 'positive', '''
seed()
assert call('AdjustLimits',[['TMparam',eq,3.4,{Tolerance:0.1}],['TMparam1',eq,10,{Tolerance:2}]])
row=definition();equal(round(row[LoYel],8),3.3);equal(round(row[HiYel],8),3.5)
equal(definition('TMparam1')[LoRed],8);equal(definition('TMparam1')[HiRed],12)
''')
add('adjust-analog', 'boundary', '''
assert call('AdjustLimits',[['TMparam',eq,0,{Tolerance:0}]])
equal(definition()[LoRed],0);equal(definition()[HiRed],0)
equal(alarm(0),False);equal(alarm(.001),True)
''')
add('adjust-analog', 'failure', '''
seed()
unchanged(lambda:call('AdjustLimits',[['TMparam',eq,3.4,{Tolerance:.1}],['TM.CORE.MODE',eq,12]]))
unchanged(lambda:call('AdjustLimits',[['TMparam',eq,3.4,{Tolerance:-1}]]))
equal(definition()[LoRed],10)
''')
add('adjust-analog', 'recovery', '''
seed()
unchanged(lambda:call('AdjustLimits',[['TMparam',eq,3.4,{Tolerance:-1}]]))
assert call('AdjustLimits',[['TMparam',eq,25]],Tolerance=5)
equal(definition()[LoRed],20);equal(definition()[HiRed],30)
equal(alarm(25),False)
''')

add('adjust-status', 'positive', STATUS_SEED+'''
assert call('AdjustLimits',[['TM.CORE.MODE',eq,['SAFE']]])
row=definition('TM.CORE.MODE')
equal(row[Nominal],['NOMINAL','SAFE']);equal(row[Warning],[]);equal(row[Error],['FAILED'])
equal(alarm('SAFE','TM.CORE.MODE'),False)
''')
add('adjust-status', 'boundary', STATUS_SEED+'''
assert call('AdjustLimits',[['TM.CORE.MODE',eq,['SAFE','OFF']]])
row=definition('TM.CORE.MODE');equal(row[Ignore],[]);equal(row[Warning],[])
assert call('AdjustLimits',[['TM.CORE.MODE',eq,['SAFE']]])
equal(definition('TM.CORE.MODE')[Nominal],['NOMINAL','SAFE','OFF'])
''')
add('adjust-status', 'failure', STATUS_SEED+'''
unchanged(lambda:call('AdjustLimits',[['TM.CORE.MODE',eq,[123]]]))
unchanged(lambda:call('AdjustLimits',[['TM.CORE.MODE',eq,[]]]))
''')
add('adjust-status', 'recovery', STATUS_SEED+'''
equal(alarm('FAILED','TM.CORE.MODE'),True)
assert call('AdjustLimits',[['TM.CORE.MODE',eq,'FAILED']])
equal(definition('TM.CORE.MODE')[Error],[])
equal(alarm('FAILED','TM.CORE.MODE'),False)
''')

add('limit-file', 'positive', '''
assert call('LoadLimits','limits://normal')
equal(definition()[LoRed],0);equal(definition('TM.CORE.MODE')[Nominal],['NOMINAL'])
equal(len(ground()['limit_files']['limits://normal']),64)
''')
add('limit-file', 'boundary', '''
assert call('LoadLimits','limits://normal');before=ground()
assert call('LoadLimits','limits://normal');equal(ground(),before)
''')
add('limit-file', 'failure', '''
seed()
for uri in ('limits://missing','limits://../normal','file://normal'):
    unchanged(lambda:call('LoadLimits',uri))
''')
add('limit-file', 'recovery', '''
unchanged(lambda:call('LoadLimits','limits://missing'))
assert call('LoadLimits','limits://normal')
inject(50);assert call('RestoreNormalLimits')
equal(ground()['limits'],{});equal(call('IsAlarmed','TMparam'),False)
assert call('LoadLimits','limits://normal');equal(definition()[LoRed],0)
''')

add('paired-properties', 'positive', '''
seed();assert call('SetLimits','TMparam',LoBoth=5,HiBoth=45)
row=definition();equal([row[LoRed],row[LoYel],row[HiYel],row[HiRed]],[5,5,45,45])
equal(call('GetLimits','TMparam',Select='GENERIC',Value=Midpoint),25)
equal(call('GetLimits','TMparam',Select='GENERIC',Value=Tolerance),20)
''')
add('paired-properties', 'boundary', '''
assert call('SetLimits','TMparam',Midpoint=0,Tolerance=0)
equal(call('GetLimits','TMparam',Select='GENERIC',Value=Tolerance),0)
equal(alarm(0),False)
''')
add('paired-properties', 'failure', '''
seed()
unchanged(lambda:call('SetLimits','TMparam',LoBoth=5,LoRed=4))
unchanged(lambda:call('GetLimits','TMparam',Select=ALL,Value=Midpoint))
''')
add('paired-properties', 'recovery', '''
seed()
unchanged(lambda:call('SetLimits','TMparam',Midpoint=0,Tolerance=-1))
assert call('SetLimits','TMparam',Midpoint=25,Tolerance=5)
equal(call('GetLimits','TMparam',Select='GENERIC',Value=Midpoint),25)
equal(alarm(25),False)
''')

# Literal manual read/edit/write flows supplement the backend feature probes.
add('round-trip', 'positive', '''
assert call('SetLimits','TMparam',Limits={'ID1':dict(HARD)})
ld=call('GetLimits','TMparam',Select=ACTIVE)
ld['ID1'][LoRed]=0.5
assert call('SetLimits','TMparam',Limits=ld)
equal(call('GetLimits','TMparam',Select='ID1',Value=LoRed),0.5)
mydef=call('GetLimits','TMparam',Select=ACTIVE)['ID1']
mydef[LoRed]=0.25
assert call('SetLimits','TMparam',Definition=mydef,Select='ID1')
equal(call('GetLimits','TMparam',Select='ID1',Value=LoRed),0.25)
equal(ld['ID1'][LoRed],0.5)
''')
add('round-trip', 'boundary', '''
assert call('SetLimits','TMparam',Limits={'ID1':dict(HARD),'ID2':dict(HARD,Active=False)})
ld=call('GetLimits','TMparam',Select=ALL)
ld['ID1'][LoRed]=0;ld['ID2'][HiRed]=100
assert call('SetLimits','TMparam',Limits=ld)
equal(call('GetLimits','TMparam',Select=ALL),ld)
equal(list(call('GetLimits','TMparam',Select=ACTIVE)),['ID1'])
''')
add('round-trip', 'failure', '''
assert call('SetLimits','TMparam',Limits={'ID1':dict(HARD),'ID2':dict(HARD)})
ld=call('GetLimits','TMparam',Select=ALL)
ld['ID1'][LoRed]=0;ld['ID2'][HiRed]=1
unchanged(lambda:call('SetLimits','TMparam',Limits=ld))
equal(call('GetLimits','TMparam',Select='ID1',Value=LoRed),10)
equal(call('GetLimits','TMparam',Select='ID2',Value=HiRed),40)
''')
add('round-trip', 'recovery', '''
assert call('SetLimits','TM.CORE.MODE',Limits={'ID1':{Nominal:['NOMINAL'],Warning:['SAFE'],Error:['FAILED'],Ignore:[]}})
ld=call('GetLimits','TM.CORE.MODE',Select=ACTIVE)
mydef=ld['ID1'];mydef[Nominal]=['SAFE']
unchanged(lambda:call('SetLimits','TM.CORE.MODE',Definition=mydef,Select='ID1'))
mydef[Nominal]=['VALUE']
assert call('SetLimits','TM.CORE.MODE',Definition=mydef,Select='ID1')
equal(call('GetLimits','TM.CORE.MODE',Select='ID1',Value=Nominal),['VALUE'])
equal(alarm('VALUE','TM.CORE.MODE'),False)
''')

add('selectors', 'positive', '''
assert call('SetLimits','TMparam',Limits={'ID1':dict(HARD),'ID2':dict(HARD),'ID3':dict(HARD,Active=False)})
assert call('SetLimits','TMparam',Definition={LoRed:5})
equal([call('GetLimits','TMparam',Select=k,Value=LoRed) for k in ('ID1','ID2','ID3')],[5,5,10])
assert call('SetLimits','TMparam',Definition={HiRed:45},Select=ALL)
equal([call('GetLimits','TMparam',Select=k,Value=HiRed) for k in ('ID1','ID2','ID3')],[45,45,45])
''')
add('selectors', 'boundary', '''
assert call('SetLimits','TMparam',Type=SPIKE,Limits={'ID1':{Delta:1},'ID2':{Delta:2,Active:False}})
assert call('SetLimits','TMparam',Select=ALL,Delta=0.23)
equal([call('GetLimits','TMparam',Select=k,Value=Delta) for k in ('ID1','ID2')],[0.23,0.23])
assert call('SetLimits','TMparam',Select=ACTIVE,Delta=0.30)
equal([call('GetLimits','TMparam',Select=k,Value=Delta) for k in ('ID1','ID2')],[0.30,0.23])
''')
add('selectors', 'failure', '''
assert call('SetLimits','TMparam',Limits={'ID1':dict(HARD,Active=False)})
unchanged(lambda:call('SetLimits','TMparam',Definition={LoRed:5}))
unchanged(lambda:call('SetLimits','TMparam',Definition={LoRed:5},Select='UNKNOWN'))
equal(call('GetLimits','TMparam',Select=ACTIVE),{})
''')
add('selectors', 'recovery', '''
assert call('SetLimits','TMparam',Limits={'ID1':dict(HARD,Active=False)})
unchanged(lambda:call('SetLimits','TMparam',LoRed=5))
assert call('SetLimits','TMparam',Definition={Active:True},Select='ID1')
assert call('SetLimits','TMparam',LoRed=5)
equal(call('GetLimits','TMparam',Select='ID1',Value=LoRed),5)
''')

add('properties', 'positive', '''
values={Nominal:['NOMINAL'],Warning:['SAFE'],Error:['FAILED','UNKNOWN'],Ignore:[],Hysteresis:1,Active:True,Name:'ID1 Status check',Type:STATUS}
assert call('SetLimits','TM.CORE.MODE',Limits={'ID1':values})
equal(call('GetLimits','TM.CORE.MODE',Select='ID1'),values)
equal(call('GetLimits','TM.CORE.MODE',Select='ID1',Value=Error),['FAILED','UNKNOWN'])
equal(call('GetLimits','TM.CORE.MODE',Select='ID1',Value=Ignore),[])
equal(call('GetLimits','TM.CORE.MODE',Select='ID1',Value=Type),STATUS)
''')
add('properties', 'boundary', '''
assert call('SetLimits','TM.CORE.MODE',Definition={Nominal:'NOMINAL',Warning:'SAFE',Error:'FAILED',Ignore:'OFF'})
for field,value in ((Nominal,'NOMINAL'),(Warning,'SAFE'),(Error,'FAILED'),(Ignore,'OFF')):
    equal(call('GetLimits','TM.CORE.MODE',Select='GENERIC',Value=field),[value])
seed();equal(call('GetLimits','TMparam',Select='GENERIC',Value=LoRed),10)
''')
add('properties', 'failure', '''
seed()
unchanged(lambda:call('GetLimits','TMparam',Value=Type))
unchanged(lambda:call('GetLimits','TMparam',Select=ACTIVE,Value=LoRed))
unchanged(lambda:call('GetLimits','TMparam',Select='GENERIC',Value=Error))
''')
add('properties', 'recovery', '''
seed()
unchanged(lambda:call('GetLimits','TMparam',Select='GENERIC',Value='LoHigh'))
equal(call('GetLimits','TMparam',Select='GENERIC',Value=LoYel),20)
unchanged(lambda:call('SetLimits','TMparam',Definition={'LoHigh':30}))
assert call('SetLimits','TMparam',Definition={LoYel:19})
equal(call('GetLimits','TMparam',Select='GENERIC',Value=LoYel),19)
''')

add('adjust-filter', 'positive', '''
seed()
assert call('AdjustLimits',[['TMparam',eq,25,{Tolerance:5}],['TMparam1',gt,99]])
equal(definition()[LoRed],20);equal(definition()[HiRed],30)
equal('TMparam1' in ground()['limit_definitions'],False)
''')
add('adjust-filter', 'boundary', '''
before=snapshot()
equal(call('AdjustLimits',[['TMparam',gt,99]]),False)
equal(snapshot(),before)
''')
add('adjust-filter', 'failure', '''
seed()
unchanged(lambda:call('AdjustLimits',[['TMparam',eq,25,{Tolerance:5}],['TMparam1',eq,10,'bad']]))
equal(definition()[LoRed],10)
''')
add('adjust-filter', 'recovery', '''
seed()
unchanged(lambda:call('AdjustLimits',[]),SyntaxException)
assert call('AdjustLimits',[['TMparam',eq,25,{Tolerance:5}],['ABSENT',neq,0]])
equal(definition()[LoRed],20);equal(alarm(25),False)
''')
