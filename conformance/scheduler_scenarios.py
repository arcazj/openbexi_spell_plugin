"""Small traced procedures with independent clocks and literal IPC expectations."""
import textwrap

HEADER = '''import datetime,json,time
from pathlib import Path
from spell.lang.functions import WaitFor
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException,SyntaxException
CFG={'HandleError':False,'PromptUser':False}
observed={}
def rejected(operation):
    try: operation()
    except (DriverException,SyntaxException) as error:
        observed.setdefault('rejected',[]).append(type(error).__name__+': '+str(error))
        return
    raise AssertionError('Invalid scheduler input was accepted')
def absolute(epoch):
    return datetime.datetime.fromtimestamp(epoch,datetime.timezone.utc).strftime('%d-%b-%Y %H:%M:%S')
'''
SCENARIOS={}


def case(group,dimension,body,**expected):
    name=group+'-'+dimension
    source=HEADER+textwrap.dedent(body)+"\nPath('assertions.json').write_text(json.dumps(observed))\n"
    compile(source,name,'exec')
    SCENARIOS[name]=dict(source=source,dimension=dimension,
        contracts=['CMP-LRM244-MODIFIER-'+group.upper()],**expected)


case('until','positive','''
target=int(time.time())+2
started=time.monotonic()
assert WaitFor(Until=TIME(absolute(target)),config=CFG) is True
observed.update(target=target,finished=time.time(),elapsed=time.monotonic()-started)
assert observed['finished']>=target
assert observed['elapsed']<5
''',waiting=True)
case('until','boundary','''
started=time.monotonic()
assert WaitFor(Until='01-Jan-1970 00:00:00',config=CFG) is True
assert WaitFor(Until=TIME(absolute(int(time.time())-1)),config=CFG) is True
observed['elapsed']=time.monotonic()-started
assert observed['elapsed']<3
target=int(time.time())+2
assert WaitFor(Until=absolute(target),config=CFG) is True
observed.update(target=target,finished=time.time())
assert observed['finished']>=target
''',waiting=True)
case('until','failure','''
for value in (1,1.5,TIME('+00:00:01'),'+00:00:01','not-a-date'):
    rejected(lambda:WaitFor(Until=value,config=CFG))
assert len(observed['rejected'])==5
''',no_waiting=True)
case('until','recovery','''
rejected(lambda:WaitFor(Until='not-a-date',config=CFG))
target=int(time.time())+2
assert WaitFor(Until=TIME(absolute(target)),config=CFG) is True
observed.update(target=target,finished=time.time())
assert observed['finished']>=target
''',waiting=True)
case('message','positive','''
started=time.monotonic()
assert WaitFor(2.4,Interval=.6,Message='SCHED:message:positive',config=CFG) is True
observed['elapsed']=time.monotonic()-started
assert observed['elapsed']>=2.4
''',waiting=True,message='SCHED:message:positive',minimum_messages=2,minimum_spacing=.4)
case('message','boundary','''
started=time.monotonic()
assert WaitFor(1.6,Interval=[.6,.2],Message='SCHED:message:boundary: caf\u00e9\\nsecond line',config=CFG) is True
observed['elapsed']=time.monotonic()-started
assert observed['elapsed']>=1.6
''',waiting=True,message='SCHED:message:boundary: caf\u00e9\nsecond line',minimum_messages=2,minimum_spacing=.1)
case('message','failure','''
rejected(lambda:WaitFor(1,Interval=.2,Message='',config=CFG))
rejected(lambda:WaitFor(1,Interval=.2,config=CFG))
rejected(lambda:WaitFor(1,Interval=.2,Message=42,config=CFG))
assert len(observed['rejected'])==3
''',no_waiting=True)
case('message','recovery','''
rejected(lambda:WaitFor(1,Interval=.2,Message='',config=CFG))
assert WaitFor(1.4,Interval=.4,Message='SCHED:message:recovery',config=CFG) is True
observed['continued']=True
''',waiting=True,message='SCHED:message:recovery',minimum_messages=2,minimum_spacing=.2)
case('message','integer-control','''
assert WaitFor(3.4,Interval=1,Message='SCHED:message:integer-control',config=CFG) is True
''',waiting=True,message='SCHED:message:integer-control',minimum_messages=2,minimum_spacing=.8)
SCENARIOS['message-integer-control'].update(contracts=[],dimension='regression')
