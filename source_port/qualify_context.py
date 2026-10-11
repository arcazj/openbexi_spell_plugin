"""Original listener/context startup and IPC shutdown. SPDX-License-Identifier: GPL-3.0-or-later."""
import ctypes
import threading
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
from service_recovery_fixtures import write_service
from cif_fixtures import write_procedures as write_cif_procedures

from live_reconnect_fixtures import write_fixture

# Adopt only this private test's orphaned children, so an attached context can
# observe process disappearance even in a Docker build without a reaping init.
assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0

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
cif_scenarios=write_cif_procedures(output/'executor-data/Procedures')

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
    completed_lifecycles=[]
    service_checkpoint_rejections=0
    def run_context(self,server=False,iteration=0,service=False,controller=None,missing_reconnect=False,service_recovery=None,pending_service_pid=None,live_reconnect=None):
        log_before=set(logs.glob('*.log'))
        label=('live-'+live_reconnect if live_reconnect else 'pending-service' if pending_service_pid else 'service-'+service_recovery if service_recovery else 'missing-reconnect' if missing_reconnect else controller or ('service' if service else 'server' if server else 'context'))+'-'+str(iteration)
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
        if pending_service_pid:
            # This test owns a live /bin/sleep process, which never logs in.
            # Context cleanup must cancel the pending model without signalling
            # that unattached process or deleting the model twice.
            (runtime/'ctx_example_services.dat').write_text('pending_service,2000-01-01_000000,none,0,'+str(pending_service_pid)+'\n')
            pending_path=output/'PendingServices'
            pending_path.mkdir(exist_ok=True)
            (pending_path/'pending_service.py').write_text("""from spell.utils.spell_service import SpellService
@SpellService(name='pending_service')
class PendingService:
    def __init__(self,name): pass
    def startService(self):
        with open('/out/unexpected-pending-service-start.txt','w') as output: output.write('duplicate')
    def isAlive(self): return False
""")
            ctx=ET.fromstring(context_original)
            ET.SubElement(ctx,'servicepath').text=str(pending_path)
            context_config.write_bytes(ET.tostring(ctx))
        if service or service_recovery:
            service_path=services
            if service_recovery:
                service_path=output/('NativeServices-'+service_recovery)
                service_path.mkdir(exist_ok=True)
                write_service(service_path,service_recovery)
            ctx=ET.fromstring(context_original)
            ET.SubElement(ctx,'servicepath').text=str(service_path)
            context_config.write_bytes(ET.tostring(ctx))
        reaped={}
        reap_stop=threading.Event()
        def reap_orphan():
            starts=output/('native_live_'+live_reconnect+'-starts.txt')
            while not reap_stop.is_set():
                if starts.exists():
                    for row in starts.read_text().splitlines():
                        fields=row.split()
                        if len(fields)!=2: continue
                        pid=int(fields[0])
                        if pid in reaped: continue
                        try:
                            child,status=os.waitpid(pid,os.WNOHANG)
                            if child: reaped[child]=status
                        except ChildProcessError: pass # not orphaned/adopted yet
                reap_stop.wait(.02)
        if live_reconnect:
            fixture=output/'executor-data/Procedures'
            if live_reconnect=='service':
                fixture=output/'LiveServices';fixture.mkdir(exist_ok=True)
                ctx=ET.fromstring(context_original)
                ET.SubElement(ctx,'servicepath').text=str(fixture)
                context_config.write_bytes(ET.tostring(ctx))
            write_fixture(fixture,live_reconnect=='service')
            reaper=threading.Thread(target=reap_orphan,name='owned-orphan-reaper')
            reaper.start()
        with (output/(label+'-listener.log')).open('wb') as log:
            process=subprocess.Popen([str(output/'SPELL-Listener'),'-c',str(config)],
                env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                # The listener opens both sockets before starting its context.
                time.sleep(.5)
                try:
                    result=subprocess.run([str(output/'context_peer'),'19980']+(['--live-'+live_reconnect] if live_reconnect else ['--pending-service'] if pending_service_pid else ['--service-'+service_recovery] if service_recovery else [controller] if controller else ['--service'] if service else ['--server'] if server else []),env=dict(environment,OPENBEXI_QUALIFICATION_PGID=str(process.pid)),
                        capture_output=True,text=True,timeout=50)
                except subprocess.TimeoutExpired as error:
                    (output/(label+'-peer.log')).write_bytes((error.stdout or b'')+(error.stderr or b''))
                    raise
                (output/(label+'-peer.log')).write_text(result.stdout+result.stderr)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('CONTEXT_STARTED',result.stdout)
                self.assertIn('CONTEXT_CLOSED',result.stdout)
                if live_reconnect:
                    self.assertIn('LIVE_CONTEXT_RECONNECT_VERIFIED '+live_reconnect,result.stdout)
                    prefix='native_live_'+live_reconnect
                    started=(output/(prefix+'-starts.txt')).read_text().splitlines()
                    self.assertEqual(len(started),1,'Reconnection restarted the Python body')
                    pid=int(started[0].split()[0])
                    self.assertEqual((output/(prefix+'-closed.txt')).read_text(),str(pid))
                    deadline=time.monotonic()+3
                    while pid not in reaped and time.monotonic()<deadline: time.sleep(.02)
                    self.assertIn(pid,reaped,'Adopted child was not reaped')
                    self.assertTrue(os.WIFEXITED(reaped[pid]))
                    self.assertEqual(os.WEXITSTATUS(reaped[pid]),0)
                    self.assertIn('RECONNECTED_CHILD_RESUMED '+live_reconnect,result.stdout)
                if controller:
                    self.assertIn('CONTROLLER_SCENARIO_COMPLETE '+controller,result.stdout)
                    for name,value in [('native_shared','roundtrip'),('native_child_parent','42'),('native_wait','waited')]:
                        if controller==name: self.assertEqual((output/(name+'-result.txt')).read_text(),value)
                    if controller=='native_child_parent':
                        self.assertEqual((output/'native_child-result.txt').read_text(),'42')
                    if controller=='native_controls':
                        self.assertEqual((output/(controller+'-result.txt')).read_text(),'42')
                        self.assertEqual((output/'native_controls-quoted.txt').read_text(),'literal argument')
                        self.assertIn('QUOTED_PROCEDURE_COMPLETE',result.stdout)
                    if controller=='native_prompt': self.assertEqual((output/(controller+'-result.txt')).read_text(),'answered')
                    if controller=='native_failure': self.assertEqual((output/(controller+'-closed.txt')).read_text(),'unwound')
                    if controller in ('native_pause','native_abort'):
                        self.assertGreaterEqual(int((output/(controller+'-closed.txt')).read_text()),0)
                if service_recovery:
                    self.assertIn('SERVICE_RESTART_VERIFIED '+service_recovery,result.stdout)
                    prefix=output/('service-'+service_recovery)
                    started=[int(v) for v in Path(str(prefix)+'-starts.txt').read_text().splitlines()]
                    closed=[int(v) for v in Path(str(prefix)+'-closed.txt').read_text().splitlines()]
                    self.assertEqual(len(started),2)
                    self.assertEqual(len(set(started)),2)
                    self.assertEqual(closed,started if service_recovery=='failure' else started[1:])
                    for pid in started:
                        with self.assertRaises(ProcessLookupError): os.kill(pid,0)
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
                if live_reconnect:
                    time.sleep(.1) # allow the private reaper to drain killed children
                    reap_stop.set();reaper.join(timeout=2)
                    self.assertFalse(reaper.is_alive())
        text=(output/(label+'-listener.log')).read_text(errors='replace')
        self.assertNotIn('AddressSanitizer:',text)
        self.assertNotIn('runtime error:',text)
        self.assertNotIn('Fatal Python error:',text)
        native_logs='\n'.join(path.read_text(errors='replace') for path in set(logs.glob('*.log'))-log_before)
        self.assertFalse('try kill' in native_logs,'Executor required a forced kill; see native logs')
        self.assertFalse('killing instead' in native_logs,'Context required a forced kill; see native logs')
        self.assertIn('Context process finished: CTX_example',native_logs)
        self.assertIn('Closed context',native_logs)
        if service_recovery:
            self.assertIn('[***] End main loop',native_logs)
            if service_recovery=='failure':
                self.assertIn('intentional service failure',native_logs)
        if missing_reconnect:
            self.assertIn('Reconnecting executor native_server#999',native_logs)
        if pending_service_pid:
            self.assertIn('Reconnecting service pending_service',native_logs)
            self.assertIn('Service watchdog retained pending reconnect: pending_service',native_logs)
            self.assertFalse((output/'unexpected-pending-service-start.txt').exists(),'Watchdog started a duplicate pending service')
        if controller:
            self.assertIn('[***] End main loop',native_logs)
        if live_reconnect:
            self.assertNotIn('Unable to pause procedure',native_logs)
            self.assertNotIn('Failed to close executor',native_logs)
        if service:
            self.assertIn('[***] End main loop',native_logs)
            self.assertIn('Executor process finished: native_service',native_logs)
        if server:
            self.assertIn('[***] End main loop',native_logs)
            self.assertIn('Executor process finished: native_server#1',native_logs)
        self.completed_lifecycles.append(label)


    def test_live_native_processes_reconnect_after_context_crash(self):
        for kind in ('executor','service'):
            for iteration in range(3):
                with self.subTest(kind=kind,iteration=iteration):
                    self.run_context(live_reconnect=kind,iteration=iteration)

    def test_child_shared_data_and_scheduler_cif(self):
        for scenario in cif_scenarios:
            with self.subTest(scenario=scenario): self.run_context(controller=scenario)

    def test_service_watchdog_restarts_failed_native_process(self):
        for scenario in ('failure','crash'):
            with self.subTest(scenario=scenario): self.run_context(service_recovery=scenario)

    def test_service_checkpoint_request_is_rejected_before_startup(self):
        marker=output/'unexpected-service-recovery-start.txt'
        procedure=output/'service-recovery-must-not-start.py'
        procedure.write_text("from pathlib import Path\nPath("+repr(str(marker))+").write_text('started')\n")
        checkpoint=output/'requested-service-checkpoint.dat'
        original=b'Preserve the requested checkpoint without opening it as a continuation.\n'
        checkpoint.write_bytes(original)
        for warm in (False,True):
            with self.subTest(warm=warm):
                args=[str(output/'SPELL-Service_v3'),'-f',str(procedure),'-c',str(config),
                      '-n','example','-r',str(checkpoint)]+(['-w'] if warm else [])
                result=subprocess.run(args,capture_output=True,text=True,timeout=5,env=environment)
                text=result.stdout+result.stderr
                (output/('service-checkpoint-rejection-'+str(int(warm))+'.log')).write_text(text)
                self.assertEqual(result.returncode,1,text)
                self.assertIn('Checkpoint recovery is unavailable for native services',text)
                self.assertFalse(marker.exists(),'Rejected service recovery executed Python code')
                self.assertEqual(checkpoint.read_bytes(),original)
                self.assertNotIn('AddressSanitizer:',text)
                self.assertNotIn('runtime error:',text)
                type(self).service_checkpoint_rejections+=1

    def test_context_close_cancels_missing_executor_reconnect(self):
        self.run_context(missing_reconnect=True)

    def test_context_close_cancels_pending_service_once(self):
        with subprocess.Popen(['/bin/sleep','60']) as owned:
            try:
                self.run_context(pending_service_pid=owned.pid)
                self.assertIsNone(owned.poll(),'Context signalled an unattached pending service')
            finally:
                if owned.poll() is None: owned.terminate()
                owned.wait(timeout=5)

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


selection=os.environ.get('OPENBEXI_CONTEXT_TEST_FILTER','all')
if selection=='all': suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContextTests)
elif selection=='live-reconnect': suite=unittest.TestSuite([ContextTests('test_live_native_processes_reconnect_after_context_crash')])
else: raise ValueError('Unknown context qualification selection: '+selection)
result=unittest.TextTestRunner(verbosity=2).run(suite)
(output/'context-runtime.json').write_text(json.dumps({'tests':result.testsRun,'service_checkpoint_rejections':ContextTests.service_checkpoint_rejections,'lifecycle_runs':len(ContextTests.completed_lifecycles),'completed_lifecycles':ContextTests.completed_lifecycles,'selection':selection,'live_reconnect_scenarios':['executor','service'],'pending_service_cancelled':True,'cif_scenarios':list(cif_scenarios),'service_restart_scenarios':['failure','crash'],'missing_reconnect_cancelled':True,'service_runs':1,'controller_scenarios':list(controller_scenarios),
    'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)},indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
