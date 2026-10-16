"""LRM116 RESUME is a driver extension; exercise the original extension hooks."""
from memory_native_cases import HEADER

HEADER=HEADER.replace("value=getattr(api,name)(*args,HandleError=False,PromptUser=False,**options)",
    "options.setdefault('HandleError',False);options.setdefault('PromptUser',False)\n        value=getattr(api,name)(*args,**options)")
EXTENSION='''
from types import MethodType
from spell.lib.registry import REGISTRY
from spell.lib.adapter.constants.core import KEY_SEPARATOR
interface=REGISTRY['TC']
original={name:getattr(interface,name) for name in ('_sendList','driverUpdateActionList','driverBeforeAction','driverPerformAction','driverAfterAction')}
original_single=interface._sendCommand
observed['driver']=[]
pending=[]
state={'cursor':0,'interrupted':False,'allow_resume':ALLOW_RESUME}

def event(action,**values):
    observed['driver'].append(dict(action=action,cursor=state['cursor'],**values));save()

def continue_group(config):
    while state['cursor']<len(pending):
        item=pending[state['cursor']]
        if not original_single(item,config):return False
        event('command-completed',name=item.name())
        state['cursor']+=1
    return True

def injection(self,items,config=None):
    event('injection',members=[item.name() for item in items])
    if pending:
        assert [item.name() for item in items]==[item.name() for item in pending]
        return continue_group(config)
    pending.extend(items);state['config']=config
    while state['cursor']<FAIL_AT:
        item=pending[state['cursor']]
        assert original_single(item,config)
        event('command-completed',name=item.name());state['cursor']+=1
    state['interrupted']=True
    event('driver-interruption')
    raise DriverException('Extension fixture interruption before next command')

def choices(self,options,exception=None):
    assert state['interrupted'] and state['config'][OnFailure]&RESUME
    event('choices',standard=list(options))
    return list(options)+['Z'+KEY_SEPARATOR+'Resume pending driver commands']

def before(self,code):event('before',code=code)
def action(self,code):
    assert code=='Z';event('perform',code=code)
    if not state['allow_resume']:return [False,False]
    return [False,continue_group(state['config'])]
def after(self,code):event('after',code=code)

for name,method in (('_sendList',injection),('driverUpdateActionList',choices),
    ('driverBeforeAction',before),('driverPerformAction',action),('driverAfterAction',after)):
    setattr(interface,name,MethodType(method,interface))
fixture('feed',enabled=True)
'''
CASES={}
for dimension,fail_at,allow,policy,expected,recover in (
    ('positive',1,True,'RESUME',True,False),
    ('boundary',0,True,'RESUME|CANCEL',True,False),
    ('failure',1,False,'RESUME',False,False),
    ('recovery',1,False,'RESUME',False,True),
):
    extension=EXTENSION.replace('FAIL_AT',str(fail_at)).replace('ALLOW_RESUME',repr(allow))
    invocation="call('Send',group=['CMD1','CMD2','CMD3'],Confirm=False,Wait=False,HandleError=True,PromptFailure=True,OnFailure="+policy+")"
    body='\ntry:\n    equal('+invocation+','+repr(expected)+')\n'
    if recover:body+="    state['allow_resume']=True\n    equal("+invocation+",True)\n"
    body+="    equal(state['cursor'],"+str(3 if expected or recover else 1)+")\nfinally:\n    for name,method in original.items():setattr(interface,name,method)\n"
    source=HEADER+extension+body+"\nFilePath('result.json').write_text(json.dumps({'completed':True}))\n"
    compile(source,'driver-extension:'+dimension,'exec')
    CASES['resume-extension:'+dimension]=dict(feature='resume-extension',dimension=dimension,source=source,
        expected_members=['CMD1','CMD2','CMD3'] if expected or recover else ['CMD1'],
        expected_choices=['Q','Z'] if dimension=='boundary' else ['Z'],
        scope='Original driver extension hooks with an explicit per-session fixture driver; no claim that GENERIC implements RESUME itself')
