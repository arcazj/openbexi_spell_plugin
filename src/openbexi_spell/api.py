"""Retained socket SDK and explicit runtime binding for bounded SPELL profiles."""
from contextvars import ContextVar
import json
import os
import socket
import threading

ENG, RAW = 'ENG', 'RAW'
OK, YES_NO, ALPHA, NUM, DATE, COMBO, LIST = 'OK', 'YES_NO', 'ALPHA', 'NUM', 'DATE', 'COMBO', 'LIST'

class DriverException(Exception):
    def __init__(self, message, reason='unknown', *, code=0, operation=None, effect_certainty='NO_EFFECT'):
        if type(code) is not int or effect_certainty not in {'NO_EFFECT','CONFIRMED','UNKNOWN'}:
            raise ValueError('invalid driver failure metadata')
        self.message,self.reason,self.code=str(message),str(reason),code
        self.operation,self.effect_certainty=operation,effect_certainty
        super().__init__(self.message+' ( '+self.reason+' )')

class Command:
    __slots__=('_encoded',)
    def __init__(self, value):
        self._encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    def as_dict(self): return json.loads(self._encoded)

class Broker:
    def __init__(self):
        self.pid=os.getpid();self.sequence=0;self.channel=None;self.buffer=bytearray()
    def invoke(self,name,args,modifiers):
        if os.getpid()!=self.pid or threading.current_thread() is not threading.main_thread():
            raise DriverException('SPELL calls require the original main thread','CALLER_IDENTITY',operation=name)
        if self.channel is None:
            descriptor=os.environ.get('SPELL_BROKER_FD')
            if descriptor is None:
                raise DriverException('native SPELL broker is unavailable','BROKER_UNAVAILABLE',operation=name)
            self.channel=socket.socket(fileno=int(descriptor));self.channel.set_inheritable(False)
        self.sequence+=1
        message={'schema':'spell.native-call/1','sequence':self.sequence,'operation':name,'args':list(args),'modifiers':modifiers}
        raw=json.dumps(message,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        if len(raw)>32768: raise ValueError('SPELL call exceeds its byte bound')
        self.channel.sendall(raw+b'\n')
        while b'\n' not in self.buffer:
            chunk=self.channel.recv(8192)
            if not chunk:
                raise DriverException('native SPELL transport was lost','BROKER_LOST',operation=name,effect_certainty='UNKNOWN' if name=='Send' else 'NO_EFFECT')
            self.buffer.extend(chunk)
            if len(self.buffer)>65536: raise ValueError('SPELL response exceeds its byte bound')
        raw,_,remaining=self.buffer.partition(b'\n');self.buffer[:]=remaining
        result=json.loads(raw)
        if set(result)!={'sequence','value','error'} or result['sequence']!=self.sequence:
            raise ValueError('SPELL response binding differs')
        if result['error'] is not None: raise DriverException(operation=name,**result['error'])
        return result['value']

class SpellContext:
    def __init__(self,runtime=None):
        self.runtime=runtime or Broker();self.policy=None
    def configuration(self):
        if self.policy is None:
            from .common import SpellContext as Policy
            config=self.runtime.invoke('_Config',(),{})
            self.policy=Policy(config['defaults'],max_verbosity=config['max_verbosity'],retry_budget=config['retry_budget'])
        return self.policy
    def invoke(self,name,args,modifiers):
        from .common import _FUNCTIONS,_COMMON
        policy=self.configuration()
        def operation(config):
            options={key:config[key] for key in _FUNCTIONS[name] if key not in _COMMON}
            if name=='Display':options['Verbosity']=config['Verbosity']
            return self.runtime.invoke(name,args,options)
        def prompt(operation,choices,outcome):
            from .common import Action
            detail=({'code':outcome.code,'effect_certainty':outcome.effect_certainty}
                    if isinstance(outcome,DriverException) else outcome)
            return Action(self.runtime.invoke('_PolicyPrompt',(operation,int(choices),detail),{}))
        def notify(operation,result,failure):
            detail=None if failure is None else {'code':failure.code,'reason':failure.reason,'effect_certainty':failure.effect_certainty}
            self.runtime.invoke('_Notify',(operation,result,detail),{})
        return policy.invoke(name,operation,modifiers=modifiers,prompt=prompt,notify=notify,
            abort=lambda operation,failure:self.runtime.invoke('_Abort',(operation,),{}))

_context=ContextVar('native_spell_context',default=None)
def current_context():
    context=_context.get()
    if context is None: context=SpellContext();_context.set(context)
    return context

def GetTM(item,**modifiers): return current_context().invoke('GetTM',(item,),modifiers)
def Verify(item,expected,**modifiers): return current_context().invoke('Verify',(item,expected),modifiers)
def WaitFor(target,**modifiers):
    from .time import TIME
    if isinstance(target,TIME):
        target=target.rel() if target.isRel() else {'at':target.value().isoformat()}
    return current_context().invoke('WaitFor',(target,),modifiers)
def BuildTC(name,arguments=None,**modifiers):
    if arguments is not None and type(arguments) is not dict:raise TypeError('BuildTC arguments must be a dictionary')
    value=current_context().invoke('BuildTC',(name,{} if arguments is None else arguments),modifiers)
    return Command(value) if type(value) is dict else value
def Send(command,**modifiers):
    if type(command) is str: command=BuildTC(command)
    if not isinstance(command,Command): raise TypeError('Send requires a BuildTC command')
    return current_context().invoke('Send',(command.as_dict(),),modifiers)
def Display(message,**modifiers): return current_context().invoke('Display',(message,),modifiers)
def Prompt(message,**modifiers): return current_context().invoke('Prompt',(message,),modifiers)
def ChangeLanguageConfig(function,**modifiers):current_context().configuration().change(function,**modifiers)
for _function in (GetTM,Verify,WaitFor,BuildTC,Send,Display,Prompt): _function._spell_name=_function.__name__

def _stats(action, view_id, title, values, labels, chart, x_values, samples):
    """Local simulator extension, outside the seven SPELL common-policy calls."""
    values=list(values)
    labels=[str(i+1) for i in range(len(values))] if labels is None else list(labels)
    return current_context().runtime.invoke('_Graphics', ({'action':action,'id':view_id,
        'title':title,'values':values,'labels':labels,'chart':chart,
        'x_values':None if x_values is None else list(x_values),
        'samples':None if samples is None else list(samples)},), {})

def OpenStats(title, values, *, labels=None, chart='line', view_id='stats', x_values=None, samples=None):
    """Open a modeless statistics/chart view in the operator workspace."""
    return _stats('open',view_id,title,values,labels,chart,x_values,samples)

def UpdateStats(title, values, *, labels=None, chart='line', view_id='stats', x_values=None, samples=None):
    """Replace the samples of an already open view."""
    return _stats('update',view_id,title,values,labels,chart,x_values,samples)

def CloseStats(view_id='stats'):
    """Close the execution's named statistics view in connected browsers."""
    return current_context().runtime.invoke('_Graphics', ({'action':'close','id':view_id},), {})
