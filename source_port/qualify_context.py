"""Original listener/context startup and IPC shutdown. SPDX-License-Identifier: GPL-3.0-or-later."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import unittest
import xml.etree.ElementTree as ET
import sys
sys.path.insert(0, str(Path(__file__).parent))
from controller_fixtures import write_procedures

output=Path('/out')
config=output/'executor-config/server/server.xml'
tree=ET.parse(config)
tree.find("./listener/property[@name='ListenerPort']").text='19980'
tree.find("./listener/property[@name='ContextListenerPort']").text='19981'
ET.SubElement(tree.getroot().find('context'),'property',name='ServiceProgram').text='/source/bin/SPELL-Service'
tree.write(config,encoding='utf-8')
context_config=output/'executor-config/contexts/context_example.xml'
context_original=context_config.read_bytes()
binary=Path('/source/bin');binary.mkdir(exist_ok=True)
for name,target in [('SPELL-Context','SPELL-Context'),('SPELL-Executor','SPELL-Executor_v3'),
        ('SPELL-Executor_v3','SPELL-Executor_v3'),('SPELL-Service','SPELL-Service_v3')]:
    (binary/name).symlink_to(output/target)
logs=output/'context-logs';logs.mkdir(exist_ok=True)
(output/'executor-data/Runtime').mkdir(exist_ok=True)
environment=dict(os.environ,SPELL_HOME='/source',SPELL_DATA='/out/executor-data',
    SPELL_CONFIG='/out/executor-config',SPELL_LOG=str(logs),
    ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
    PYTHONMALLOC='malloc')


(output/'executor-data/Procedures/native_server.py').write_text("""##########
# NAME: Native server qualification
# SPACECRAFT: Y
# PYTHON VERSION: 3
##########
from spell.lang.functions import Display
from spell.runtime import ARGS
assert ARGS['value'] == 21
value = ARGS['value'] * 2
Display('NATIVE_SERVER_COMPLETE')
with open('/out/server-result.txt','w') as result:
    result.write(str(value))
""")

controller_scenarios=write_procedures(output/'executor-data/Procedures')

services=output/'executor-data/NativeServices'
services.mkdir(exist_ok=True)
(services/'native_service.py').write_text("""##########
# NAME: Native service qualification
# SPACECRAFT: Y
# PYTHON VERSION: 3
##########
from spell.utils.spell_service import SpellService

@SpellService(name='native_service')
class NativeService:
    def __init__(self,name): self.name=name
    def startService(self):
        import os,time
        from spell.lang.functions import Display
        from spell.runtime import ARGS, IVARS, PROC
        assert len(ARGS)==0
        assert PROC['NAME']=='native_service'
        IVARS['answer']=self.execute(lambda: 6*7).result(timeout=3)
        Display('NATIVE_SERVICE_COMPLETE')
        with open('/out/service-result.txt','w') as result: result.write(str(IVARS['answer']))
        with open('/out/service-pid.txt','w') as result: result.write(str(os.getpid()))
        try:
            while True: time.sleep(0.02)
        finally:
            with open('/out/service-closed.txt','w') as result: result.write(str(os.getpid()))
    def isAlive(self): return False
""")

class ContextTests(unittest.TestCase):
    def run_context(self,server=False,iteration=0,service=False,controller=None,missing_reconnect=False):
        log_before=set(logs.glob('*.log'))
        label=('missing-reconnect' if missing_reconnect else controller or ('service' if service else 'server' if server else 'context'))+'-'+str(iteration)
        # Each scenario owns a fresh registry. Preserve failed-case evidence,
        # but do not reconnect a killed child from another isolated test.
        runtime=output/'executor-data/Runtime'
        for path in runtime.glob('ctx_example_*.dat'):
            (output/(label+'-previous-'+path.name)).write_bytes(path.read_bytes())
            path.unlink()
        if missing_reconnect:
            # Port zero asks the original socket code for an unused port. The
            # nonexistent PID is never signalled by this reconnect-only path.
            (runtime/'ctx_example_executors.dat').write_text('native_server#999,2000-01-01_000000,none,0,99999999\n')
        if service:
            ctx=ET.fromstring(context_original)
            ET.SubElement(ctx,'servicepath').text=str(services)
            context_config.write_bytes(ET.tostring(ctx))
        with (output/(label+'-listener.log')).open('wb') as log:
            process=subprocess.Popen([str(output/'SPELL-Listener'),'-c',str(config)],
                env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                # The listener opens both sockets before starting its context.
                time.sleep(.5)
                try:
                    result=subprocess.run([str(output/'context_peer'),'19980']+([controller] if controller else ['--service'] if service else ['--server'] if server else []),env=environment,
                        capture_output=True,text=True,timeout=50)
                except subprocess.TimeoutExpired as error:
                    (output/(label+'-peer.log')).write_bytes((error.stdout or b'')+(error.stderr or b''))
                    raise
                (output/(label+'-peer.log')).write_text(result.stdout+result.stderr)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('CONTEXT_STARTED',result.stdout)
                self.assertIn('CONTEXT_CLOSED',result.stdout)
                if controller:
                    self.assertIn('CONTROLLER_SCENARIO_COMPLETE '+controller,result.stdout)
                    if controller=='native_controls': self.assertEqual((output/(controller+'-result.txt')).read_text(),'42')
                    if controller=='native_prompt': self.assertEqual((output/(controller+'-result.txt')).read_text(),'answered')
                    if controller=='native_failure': self.assertEqual((output/(controller+'-closed.txt')).read_text(),'unwound')
                    if controller in ('native_pause','native_abort'):
                        self.assertGreaterEqual(int((output/(controller+'-closed.txt')).read_text()),0)
                if service:
                    self.assertIn('NATIVE_SERVICE_RUNNING',result.stdout)
                    self.assertIn('SERVICE_EXECUTABLE_VERIFIED',result.stdout)
                    self.assertEqual((output/'service-result.txt').read_text(),'42')
                    pid=int((output/'service-pid.txt').read_text())
                    self.assertEqual((output/'service-closed.txt').read_text(),str(pid))
                    with self.assertRaises(ProcessLookupError): os.kill(pid,0)
                if server:
                    self.assertIn('SERVER_EXECUTOR_FINISHED',result.stdout)
                    self.assertIn('SERVER_EXECUTOR_CLOSED',result.stdout)
                    self.assertEqual((output/'server-result.txt').read_text(),'42')
                process.terminate()
                self.assertEqual(process.wait(timeout=10),0)
            finally:
                # Only this private test's session/process group is targeted.
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=5)
                context_config.write_bytes(context_original)
        text=(output/(label+'-listener.log')).read_text(errors='replace')
        self.assertNotIn('AddressSanitizer:',text)
        self.assertNotIn('runtime error:',text)
        self.assertNotIn('Fatal Python error:',text)
        native_logs='\n'.join(path.read_text(errors='replace') for path in set(logs.glob('*.log'))-log_before)
        self.assertFalse('try kill' in native_logs,'Executor required a forced kill; see native logs')
        self.assertFalse('killing instead' in native_logs,'Context required a forced kill; see native logs')
        self.assertIn('Context process finished: CTX_example',native_logs)
        self.assertIn('Closed context',native_logs)
        if missing_reconnect:
            self.assertIn('Reconnecting executor native_server#999',native_logs)
        if controller:
            self.assertIn('[***] End main loop',native_logs)
        if service:
            self.assertIn('[***] End main loop',native_logs)
            self.assertIn('Executor process finished: native_service',native_logs)
        if server:
            self.assertIn('[***] End main loop',native_logs)
            self.assertIn('Executor process finished: native_server#1',native_logs)


    def test_context_close_cancels_missing_executor_reconnect(self):
        self.run_context(missing_reconnect=True)

    def test_original_server_controller_scenarios(self):
        for scenario in controller_scenarios:
            with self.subTest(scenario=scenario): self.run_context(controller=scenario)

    def test_context_launches_actual_service(self):
        self.run_context(service=True)

    def test_original_listener_starts_context_and_closes_over_ipc(self):
        for iteration in range(3):
            with self.subTest(iteration=iteration): self.run_context(iteration=iteration)

    def test_context_launches_actual_server_executor(self):
        for iteration in range(3):
            with self.subTest(iteration=iteration): self.run_context(server=True,iteration=iteration)


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContextTests))
(output/'context-runtime.json').write_text(json.dumps({'tests':result.testsRun,'lifecycle_runs':13,'missing_reconnect_cancelled':True,'service_runs':1,'controller_scenarios':list(controller_scenarios),
    'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)},indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
