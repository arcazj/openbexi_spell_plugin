"""Original WS controller + frame manager. SPDX-License-Identifier: GPL-3.0-or-later."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('_spell_analysis_qualification',next(Path('/out').glob('_spell_analysis_qualification*.so')))
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)

def worker(action, procedure, stem, subject, line, occurrence):
    if action.startswith('dta-'):
        action=action.removeprefix('dta-')
        sys.path.insert(0,'/source/src/spell')
        path=next(Path('/out').glob('libSPELL_DTA_v3*.so'))
        for name in ('libSPELL_DTA_v3','_spell_dta_qualification'):
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            sys.modules[name]=module
        module.notifications(False)
    namespace={'__name__':'_qualified_procedure'}
    handle=native.manager_create(None)
    native.manager_initialize(handle,procedure,namespace)
    native.manager_warm_configure(handle,procedure,stem,stem if action!='capture' else '',2)
    if action!='capture': native.manager_warm_action(handle,'restore')
    events=[]
    visits=0
    def observe(frame,event):
        nonlocal visits
        names=[f.f_code.co_name for f in native.manager_warm_frames(handle)]
        events.append([event,frame.f_code.co_name,frame.f_lineno,names])
        if (action in ('capture','recapture') and event==2 and frame.f_code.co_name==subject and frame.f_lineno==int(line)):
            visits+=1
            if visits==int(occurrence):
                native.manager_warm_action(handle,'save')
                os.kill(os.getpid(),signal.SIGKILL)
    try:
        status,_=native.manager_execute(handle,observe)
        namespace=native.manager_namespace(handle)
        payload={'status':status,'error':native.manager_error(),'result':namespace.get('result'),'events':events,
            'final_stack':[f.f_code.co_name for f in native.manager_warm_frames(handle)]}
        print(json.dumps(payload))
    finally: native.manager_close(handle)

if len(sys.argv)>1 and sys.argv[1]=='--worker':
    worker(*sys.argv[2:])
    raise SystemExit(0)

class WarmController(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(dir='/out')
        self.root=Path(self.directory.name)
        self.procedure=self.root/'procedure.py'
        self.stem=str(self.root/'checkpoint')
    def tearDown(self): self.directory.cleanup()
    def process(self, action, subject, line, occurrence=1):
        return subprocess.run([sys.executable,'-I',__file__,'--worker',action,str(self.procedure),self.stem,
            subject,str(line),str(occurrence)],capture_output=True,text=True,timeout=20)
    def checkpoint(self,source,subject,line,expected,*,occurrence=1,recapture=None):
        self.procedure.write_text(source,encoding='utf-8')
        result=self.process('capture',subject,line,occurrence)
        self.assertEqual(result.returncode,-signal.SIGKILL,result.stdout+result.stderr)
        self.assertTrue(Path(self.stem+'.wsp').exists())
        self.assertFalse(list(self.root.glob('checkpoint_*.ws*')))
        if recapture:
            result=self.process('recapture',*recapture)
            self.assertEqual(result.returncode,-signal.SIGKILL,result.stdout+result.stderr)
        result=self.process('resume',subject,line)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['status'],0,data)
        self.assertEqual(data['result'],expected,data)
        self.assertEqual(data['final_stack'],['<module>'])
        return data
    def test_nested_return_expression_and_stack_order(self):
        data=self.checkpoint('def child(x):\n value=x*2\n return value\ndef parent(x):\n return 100+child(x)+1\nresult=parent(7)\n','child',3,115)
        self.assertEqual(data['events'][0][1:],['child',3,['<module>','parent','child']])
        returns=[row for row in data['events'] if row[0]==3]
        self.assertEqual([row[1] for row in returns],['child','parent','<module>'])
        self.assertEqual([row[3] for row in returns],[['<module>','parent'],['<module>'],['<module>']])
    def test_recursive_operands(self):
        self.checkpoint('def run(n):\n if n==0:\n  return 1\n return n*run(n-1)+n\nresult=run(4)\n','run',3,88)
    def test_argument_kinds(self):
        self.checkpoint('def child(a, /, b=2, *args, scale=3, **kw):\n total=(a+b+sum(args)+kw["extra"])*scale\n return total\nresult=child(1,4,5,6,scale=2,extra=7)\n','child',3,46)
    def test_shared_closure_with_caller(self):
        self.checkpoint('def outer():\n value=9\n def child():\n  nonlocal value\n  value+=1\n  return value\n answer=child()\n return answer+value\nresult=outer()\n','child',5,20)
    def test_distinct_handled_exceptions(self):
        self.checkpoint('def child():\n try:\n  raise ValueError("child")\n except ValueError:\n  value=1\n return value\ntry:\n raise KeyError("parent")\nexcept KeyError:\n child()\n try:\n  raise\n except KeyError as error:\n  result=str(error)\n','child',5,"'parent'")
    def test_parent_handler_and_finally(self):
        self.checkpoint('def child():\n value=1\n raise ValueError("resumed")\ndef parent():\n try:\n  child()\n except ValueError as error:\n  return str(error)\n finally:\n  events.append("finally")\nevents=[]\nresult=(parent(),events)\n','child',3,['resumed',['finally']])
    def test_exception_skips_intermediate_caller(self):
        self.checkpoint('def child():\n value=1\n raise KeyError("resumed")\ndef parent():\n return child()\ntry:\n parent()\nexcept KeyError as error:\n result=str(error)\n','child',3,"'resumed'")
    def test_context_manager_suppresses_resumed_exception(self):
        self.checkpoint('class Context:\n def __enter__(self):\n  events.append("enter")\n def __exit__(self,*error):\n  events.append(str(error[1]))\n  return True\ndef child():\n value=1\n raise ValueError("suppressed")\nevents=[]\nwith Context():\n child()\nresult=events\n','child',9,['enter','suppressed'])
    def test_exception_group_handlers(self):
        self.checkpoint('def child():\n value=1\n raise ExceptionGroup("group",[ValueError("value"),KeyError("key")])\nresult=[]\ntry:\n child()\nexcept* ValueError as group:\n result.append(str(group.exceptions[0]))\nexcept* KeyError as group:\n result.append(str(group.exceptions[0]))\n','child',3,['value',"'key'"])
    def test_recheckpoint_resumed_child_with_pending_callers(self):
        self.checkpoint('def child():\n value=7\n value+=1\n value+=2\n return value\ndef parent():\n return 100+child()\nresult=parent()\n','child',3,110,recapture=('child',4))
    def test_recheckpoint_resumed_parent_with_new_child(self):
        self.checkpoint('def child(x):\n value=x+1\n return value\ndef parent():\n first=child(7)\n second=child(first)\n return first+second\nresult=parent()\n','child',3,17,recapture=('child',3))
    def test_c_call_boundary_cannot_publish_checkpoint(self):
        self.procedure.write_text('def child(value):\n result=value*2\n return result\nresult=sorted([1,2],key=child)\n')
        result=self.process('capture','child',2)
        self.assertNotEqual(result.returncode,-signal.SIGKILL,result.stdout+result.stderr)
        self.assertFalse(Path(self.stem+'.wsp').exists())
        self.assertEqual(json.loads(result.stdout)['status'],2)
    def test_modes_reset_and_cleanup(self):
        self.procedure.write_text('value=7\nresult=value+3\n')
        for mode in (0,1,2,3):
            with self.subTest(mode=mode):
                handle=native.manager_create(None)
                try:
                    native.manager_initialize(handle,str(self.procedure),{'__name__':'_qualified_procedure'})
                    native.manager_warm_configure(handle,str(self.procedure),self.stem,'',mode)
                    def observe(frame,event):
                        if mode==1 and event==2 and frame.f_lineno==2: native.manager_warm_action(handle,'stage')
                        if mode==2 and event==2 and frame.f_lineno==2: native.manager_warm_action(handle,'save')
                    self.assertEqual(native.manager_execute(handle,observe)[0],0,native.manager_error())
                    self.assertEqual(Path(self.stem+'.wsp').exists(),mode!=3)
                    native.manager_warm_action(handle,'reset')
                    self.assertEqual(native.manager_warm_frames(handle),[])
                    native.manager_warm_action(handle,'cleanup')
                    self.assertFalse(Path(self.stem+'.wsp').exists())
                finally: native.manager_close(handle)
    def test_fix_uses_last_line_state_after_execution_error(self):
        self.procedure.write_text('value=7\nresult=value/divisor\n')
        handle=native.manager_create(None)
        try:
            namespace={'divisor':0}
            native.manager_initialize(handle,str(self.procedure),namespace)
            native.manager_warm_configure(handle,str(self.procedure),self.stem,'',2)
            self.assertEqual(native.manager_execute(handle)[0],2)
            native.manager_warm_action(handle,'fix')
            namespace['divisor']=2
            self.assertEqual(native.manager_execute(handle)[0],0)
            self.assertEqual(namespace['result'],3.5)
        finally: native.manager_close(handle)

class DataWarm(unittest.TestCase):
    setUp=WarmController.setUp
    tearDown=WarmController.tearDown
    checkpoint=WarmController.checkpoint
    def process(self,action,subject,line,occurrence=1):
        return WarmController.process(self,'dta-'+action,subject,line,occurrence)
    def test_shared_native_data_across_callers_and_second_checkpoint(self):
        source='''from spell.lib.adapter.data import DataContainer,Var
a=DataContainer('A')
b=DataContainer('B')
v=Var(Default=7,Range=[0,10])
b[2.5]=v
a['last']=v
def child(data):
 marker=1
 data['last']=9
 return data['last']
result=(child(a),b[2.5],a.values()[0] is b.values()[0],v.__reduce_ex__(5)[2][1],v.__reduce_ex__(5)[2][3] is a)
'''
        self.checkpoint(source,'child',9,[9,9,True,'last',True],recapture=('child',10))
    def test_original_constraints_remain_active_after_recovery(self):
        source='''from spell.lib.adapter.data import DataContainer,Var
c=DataContainer('checked')
c['v']=Var(Default=7,Range=[0,10])
def run():
 rejected=False
 try:
  c['v']=99
 except Exception:
  rejected=True
 return rejected,c['v']
result=run()
'''
        self.checkpoint(source,'run',5,[True,7])
    def test_subclass_state_restores_without_constructor_side_effects(self):
        source='''from spell.lib.adapter.data import DataContainer,Var
events=[]
class Variable(Var):
 def __init__(self,**options):
  events.append('constructed')
  super().__init__(**options)
c=DataContainer('subclass')
v=Variable(Default=7)
c['v']=v
v.owner=c
def run():
 marker=1
 return c['v'],events,v.owner is c
result=run()
'''
        self.checkpoint(source,'run',13,[7,['constructed'],True])

with_data=len(sys.argv)>1 and sys.argv[1]=='--dta'
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DataWarm if with_data else WarmController))
Path('/out/'+('dta-warm' if with_data else 'warm')+'-runtime.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),
    'errors':len(result.errors),'skips':len(result.skipped),'full_spell_executor_qualified':False,
    'physical_python_caller_chain_restored':False,'address_sanitizer':True,
    'undefined_behavior_sanitizer':True,'leak_sanitizer':False},indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
