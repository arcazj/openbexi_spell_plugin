"""Original executor integration checks. SPDX-License-Identifier: GPL-3.0-or-later."""
import os
import hashlib
import json
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import textwrap
import time
import unittest
import xml.etree.ElementTree as ET

output, source = Path('/out'), Path('/source')
config = output/'executor-config'
data = output/'executor-data'
for directory in ('spell','contexts','server'):
    (config/directory).mkdir(parents=True,exist_ok=True)
for directory in ('Procedures','UserLib','SpacecraftDB','GroundDB','OutputFiles/AsRun','OutputFiles/Warmstart'):
    (data/directory).mkdir(parents=True,exist_ok=True)
shutil.copyfile(source/'config/spell/language.xml',config/'spell/language.xml')
shutil.copyfile(source/'config/server/server_example.xml',config/'server/server.xml')
ctx = ET.parse(source/'config/contexts/context_example.xml')
ET.SubElement(ctx.getroot().find('driverconfig'),'property',name='CWS').text='DSS'
for datasource in list(ctx.getroot().find('databases').findall('datasource')):
    ctx.getroot().find('databases').remove(datasource)
ctx.write(config/'contexts/context_example.xml',encoding='utf-8')
driver = ET.parse(source/'drivers/example/config/driver_example.xml')
driver.getroot().find('path').text = '/out/executor-drivers'
driver.write(config/'spell/driver_example.xml',encoding='utf-8')
shutil.copytree(source/'drivers/example/python',output/'executor-drivers/example',dirs_exist_ok=True)
driver_patches={}
for path in sorted((output/'executor-drivers/example').glob('*.py')):
    original=path.read_bytes()
    text,count=re.subn(r'^import (spell\.lib\.adapter\.\w+)\.(\w+) as superClass$',
        r'from \1 import \2 as superClass',original.decode(),flags=re.M)
    assert count in (0,1)
    if count:
        path.write_text(text)
        driver_patches[path.name]={'upstream_sha256':hashlib.sha256(original).hexdigest(),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
assert len(driver_patches)==8
(output/'executor-example-driver-patches.json').write_text(json.dumps(driver_patches,indent=2)+'\n')
for directory,name in (('SpacecraftDB','SCDB'),('GroundDB','GDB')):
    (data/directory/(name+'.DB')).write_text('# Empty local qualification database\n')


class ExecutorTests(unittest.TestCase):
    def run_code(self,body,*,arguments=None,answers=None,outside=False):
        name=self._testMethodName.removeprefix('test_')
        procedure=(output if outside else data/'Procedures')/(name+'.py')
        procedure.write_text(textwrap.dedent(body),encoding='utf-8')
        command=[str(output/'SPELL-ExecutorCmd_v3'),'-f',str(procedure),
            '-c',str(config/'server/server.xml'),'-n','example','-d']
        if arguments is not None: command+=['-g',arguments]
        if answers is not None:
            path=output/(name+'-answers.txt')
            path.write_text(answers,encoding='utf-8')
            command+=['-a',str(path)]
        try:
            result=subprocess.run(command,capture_output=True,text=True,timeout=15,
                stdin=subprocess.DEVNULL,env=dict(os.environ,SPELL_LOG='/out'))
        except subprocess.TimeoutExpired as error:
            (output/('executor-'+name+'.log')).write_bytes((error.stdout or b'')+(error.stderr or b''))
            raise
        (output/('executor-'+name+'.log')).write_text(result.stdout+result.stderr)
        self.assertNotIn('AddressSanitizer:',result.stderr)
        self.assertNotIn('runtime error:',result.stderr)
        return result

    def succeeded(self,result,marker):
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn(marker,result.stdout)
        self.assertIn('[ STATUS  ] FINISHED',result.stdout)

    def test_original_command_cold_run(self):
        result=self.run_code("from spell.lang.functions import Display\n"
            "from spell.lib.registry import REGISTRY\n"
            "assert type(REGISTRY['CONFIG']).__module__=='example.config'\n"
            "assert type(REGISTRY['TM']).__module__=='example.tm'\n"
            "Display('NATIVE_EXECUTOR_COMPLETE')\n")
        self.succeeded(result,'[ DISPLAY ] NATIVE_EXECUTOR_COMPLETE')

    def test_nested_live_calls(self):
        result=self.run_code('''
            def child(x):
                return x*2
            def parent(x):
                return 100+child(x)+1
            assert parent(7)==115
            print('NESTED_COMPLETE')
        ''')
        self.succeeded(result,'NESTED_COMPLETE')
        self.assertGreaterEqual(result.stdout.count('[  CALL  ]'),3)

    def test_ordinary_script_outside_procedure_index(self):
        self.succeeded(self.run_code("print('OUTSIDE_COMPLETE')\n",outside=True),'OUTSIDE_COMPLETE')

    def test_python_output_is_visible_before_process_exit(self):
        procedure=output/'live-output.py'
        procedure.write_text("print('LIVE_READY')\nassert input()=='continue'\nprint('LIVE_DONE')\n")
        command=[str(output/'SPELL-ExecutorCmd_v3'),'-f',str(procedure),
            '-c',str(config/'server/server.xml'),'-n','example']
        with subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
            prefix=b''
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout,selectors.EVENT_READ)
                    deadline=time.monotonic()+8
                    while b'LIVE_READY' not in prefix and time.monotonic()<deadline:
                        if selector.select(timeout=max(0,deadline-time.monotonic())):
                            chunk=os.read(process.stdout.fileno(),65536)
                            if not chunk: break
                            prefix+=chunk
                self.assertIn(b'LIVE_READY',prefix)
                stdout,stderr=process.communicate(b'continue\n',timeout=10)
                result=subprocess.CompletedProcess(command,process.returncode,(prefix+stdout).decode(),stderr.decode())
                (output/'executor-live-output.log').write_text(result.stdout+result.stderr)
                self.succeeded(result,'LIVE_DONE')
            finally:
                if process.poll() is None: process.kill(); process.wait()

    def test_explicit_imports_and_parent_default(self):
        self.succeeded(self.run_code('''
            import builtins
            assert all(name not in vars(builtins) for name in ('Step','Goto','ARGS','PROC','Display','IVARS'))
            assert 'Step' not in globals()
            from spell.runtime import Step,PROC
            assert PROC['PARENT']==''
            Step('one','Explicit namespace')
            print('IMPORT_COMPLETE')
        '''),'IMPORT_COMPLETE')

    def test_arguments_use_native_container(self):
        self.succeeded(self.run_code('''
            from spell.runtime import ARGS
            from libSPELL_DTA_v3 import DataContainer
            assert isinstance(ARGS,DataContainer)
            assert ARGS['count']==7
            assert ARGS['label']=='café'
            print('ARGUMENTS_COMPLETE')
        ''',arguments="{'count':7,'label':'café'}"),'ARGUMENTS_COMPLETE')

    def test_invalid_arguments_fail_startup(self):
        result=self.run_code("print('SHOULD_NOT_RUN')\n",arguments='[1,2]')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('arguments must evaluate to a dictionary',result.stdout+result.stderr)
        self.assertNotIn('SHOULD_NOT_RUN',result.stdout)

    def test_handled_exception_continues(self):
        self.succeeded(self.run_code('''
            events=[]
            try:
                raise ValueError('expected')
            except ValueError:
                events.append('caught')
            finally:
                events.append('finally')
            assert events==['caught','finally']
            print('HANDLED_COMPLETE')
        '''),'HANDLED_COMPLETE')

    def test_uncaught_exception_nonzero(self):
        result=self.run_code("raise ValueError('UNCAUGHT_MARKER')\n")
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('UNCAUGHT_MARKER',result.stdout)

    def test_syntax_error_nonzero(self):
        result=self.run_code('def broken(:\n')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('Syntax error',result.stdout)

    def test_real_step_and_goto(self):
        self.succeeded(self.run_code('''
            from spell.runtime import Step,Goto
            visited=[]
            Step('start','Start')
            Goto('end')
            visited.append('skipped')
            Step('end','End')
            assert visited==[]
            print('GOTO_COMPLETE')
        '''),'GOTO_COMPLETE')

    def test_native_data_notifications(self):
        result=self.run_code('''
            from libSPELL_DTA_v3 import Var,DataContainer
            data=DataContainer('probe')
            data['counter']=Var(Default=5,Range=[0,10])
            data['counter']=7
            assert data['counter']==7
            print('DTA_COMPLETE')
        ''')
        self.succeeded(result,'DTA_COMPLETE')
        self.assertIn('[  ITEM  ]',result.stdout)

    def test_invalid_binding_arguments_remain_catchable(self):
        self.succeeded(self.run_code('''
            from spell.runtime import Step,Goto
            from spell.lib.registry import REGISTRY
            operations=[lambda: Step(),lambda: Goto(),lambda: Step('a','b',invalid=True),
                lambda: REGISTRY['EXEC'].setUserAction(42,'bad',{}),
                lambda: REGISTRY['EXEC'].openSubProcedure('missing',{}),
                lambda: REGISTRY['CIF'].notify('unknown','a','b','c'),
                lambda: REGISTRY['CIF'].setSharedData(['a'],[],[],'scope')]
            for operation in operations:
                try:
                    operation()
                except (TypeError,ValueError):
                    pass
                else:
                    raise AssertionError('Invalid binding arguments accepted')
            print('VALIDATION_COMPLETE')
        '''),'VALIDATION_COMPLETE')

    def test_automatic_prompt(self):
        self.succeeded(self.run_code('''
            from spell.lang.functions import Prompt
            from spell.lang.constants import YES_NO
            from spell.lang.modifiers import Type
            answer=Prompt('Continue?',{Type:YES_NO})
            assert answer is True
            print('PROMPT_COMPLETE')
        ''',answers='Y\n'),'PROMPT_COMPLETE')

    def test_invalid_prompt_answer_is_reported(self):
        result=self.run_code('''
            from spell.runtime import Prompt,YES_NO,Type
            Prompt('Continue?',{Type:YES_NO})
            print('SHOULD_NOT_RUN')
        ''',answers='invalid\n')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('Invalid prompt answer',result.stdout+result.stderr)
        self.assertNotIn('SHOULD_NOT_RUN',result.stdout)

    def test_finish_stops_subsequent_lines(self):
        result=self.run_code("from spell.lang.functions import Finish\nFinish('FINISH_MARKER')\nprint('SHOULD_NOT_RUN')\n")
        self.succeeded(result,'FINISH_MARKER')
        self.assertNotIn('SHOULD_NOT_RUN',result.stdout)

    def test_abort_nonzero_stops_subsequent_lines(self):
        result=self.run_code("from spell.lang.functions import Abort\nAbort('ABORT_MARKER')\nprint('SHOULD_NOT_RUN')\n")
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('ABORT_MARKER',result.stdout)
        self.assertNotIn('SHOULD_NOT_RUN',result.stdout)


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ExecutorTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (output/'executor-runtime.json').write_text(json.dumps({'tests':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'cases':unittest.defaultTestLoader.getTestCaseNames(ExecutorTests)},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
