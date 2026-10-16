"""LRM p56 positional relative and absolute WaitFor inputs."""
import textwrap

HEADER = '''import datetime,json,time
from pathlib import Path
from spell.lang.functions import WaitFor
from spell.lib.adapter.utctime import TIME,SECOND
from spell.lib.exception import SyntaxException,DriverException
CFG={'HandleError':False,'PromptUser':False}
observed={}
def reject(value):
    try:
        WaitFor(value,config=CFG)
    except (SyntaxException,DriverException) as error:
        observed.setdefault('rejected',[]).append(type(error).__name__)
    else:
        raise AssertionError('Invalid time accepted')
def stamp(epoch):
    return datetime.datetime.fromtimestamp(epoch,datetime.timezone.utc).strftime('%Y/%m/%d %H:%M:%S')
'''
CASES = {}


def add(family, dimension, source, waiting):
    source = HEADER + textwrap.dedent(source) + "\nPath('result.json').write_text(json.dumps(observed))\n"
    compile(source, family + ':' + dimension, 'exec')
    CASES[family + ':' + dimension] = dict(source=source, dimension=dimension, waiting=waiting)


add('relative', 'positive', '''
elapsed=[]
for value in (2,2*SECOND,'+00:00:02'):
    began=time.monotonic()
    assert WaitFor(value,config=CFG) is True
    elapsed.append(time.monotonic()-began)
assert all(2 <= value < 5 for value in elapsed),elapsed
observed['elapsed']=elapsed
''', True)
add('relative', 'boundary', '''
began=time.monotonic()
assert WaitFor(0,config=CFG) is True
observed['zero_elapsed']=time.monotonic()-began
assert observed['zero_elapsed']<2
elapsed=[]
for value in (.25,TIME('+00:00:00.25')):
    began=time.monotonic()
    assert WaitFor(value,config=CFG) is True
    elapsed.append(time.monotonic()-began)
assert all(.25 <= value < 3 for value in elapsed),elapsed
observed['elapsed']=elapsed
''', True)
add('relative', 'failure', '''
reject('+not-a-duration')
reject('+00:00:not-seconds')
assert len(observed['rejected'])==2
''', False)
add('relative', 'recovery', '''
reject('+not-a-duration')
began=time.monotonic()
assert WaitFor('+00:00:00.5',config=CFG) is True
observed['elapsed']=time.monotonic()-began
assert .5 <= observed['elapsed'] < 3
''', True)
add('absolute', 'positive', '''
began=time.monotonic()
assert WaitFor('2008/10/03 10:45:34',config=CFG) is True
assert time.monotonic()-began<2
targets=[]
for as_object in (False,True):
    target=int(time.time())+2
    value=TIME(stamp(target)) if as_object else stamp(target)
    assert WaitFor(value,config=CFG) is True
    finished=time.time()
    assert target <= finished < target+3,(target,finished)
    targets.append(dict(target=target,finished=finished,object=as_object))
observed['targets']=targets
''', True)
add('absolute', 'boundary', '''
began=time.monotonic()
for value in ('1970/01/01 00:00:00',TIME(stamp(int(time.time())-1))):
    assert WaitFor(value,config=CFG) is True
observed['elapsed']=time.monotonic()-began
assert observed['elapsed']<2
''', False)
add('absolute', 'failure', '''
reject('2024/02/30 01:00:00')
reject('not-a-date')
assert len(observed['rejected'])==2
''', False)
add('absolute', 'recovery', '''
reject('not-a-date')
target=int(time.time())+2
assert WaitFor(stamp(target),config=CFG) is True
observed.update(target=target,finished=time.time())
assert target <= observed['finished'] < target+3
''', True)
