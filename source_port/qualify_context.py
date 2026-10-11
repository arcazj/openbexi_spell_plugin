"""Original listener/context startup and IPC shutdown. SPDX-License-Identifier: GPL-3.0-or-later."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import unittest
import xml.etree.ElementTree as ET

output=Path('/out')
config=output/'executor-config/server/server.xml'
tree=ET.parse(config)
tree.find("./listener/property[@name='ListenerPort']").text='19980'
tree.find("./listener/property[@name='ContextListenerPort']").text='19981'
tree.write(config,encoding='utf-8')
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

class ContextTests(unittest.TestCase):
    def run_context(self,server=False):
        log_before=set(logs.glob('*.log'))
        label='server' if server else 'context'
        with (output/(label+'-listener.log')).open('wb') as log:
            process=subprocess.Popen([str(output/'SPELL-Listener'),'-c',str(config)],
                env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                # The listener opens both sockets before starting its context.
                time.sleep(.5)
                try:
                    result=subprocess.run([str(output/'context_peer'),'19980']+(['--server'] if server else []),env=environment,
                        capture_output=True,text=True,timeout=50)
                except subprocess.TimeoutExpired as error:
                    (output/(label+'-peer.log')).write_bytes((error.stdout or b'')+(error.stderr or b''))
                    raise
                (output/(label+'-peer.log')).write_text(result.stdout+result.stderr)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('CONTEXT_STARTED',result.stdout)
                self.assertIn('CONTEXT_CLOSED',result.stdout)
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
        text=(output/(label+'-listener.log')).read_text(errors='replace')
        self.assertNotIn('AddressSanitizer:',text)
        self.assertNotIn('runtime error:',text)
        self.assertNotIn('Fatal Python error:',text)
        native_logs='\n'.join(path.read_text(errors='replace') for path in set(logs.glob('*.log'))-log_before)
        self.assertFalse('try kill' in native_logs,'Executor required a forced kill; see native logs')
        self.assertFalse('killing instead' in native_logs,'Context required a forced kill; see native logs')
        self.assertIn('Context process finished: CTX_example',native_logs)
        self.assertIn('Closed context',native_logs)
        if server:
            self.assertIn('[***] End main loop',native_logs)
            self.assertIn('Executor process finished: native_server#1',native_logs)


    def test_original_listener_starts_context_and_closes_over_ipc(self):
        self.run_context()

    def test_context_launches_actual_server_executor(self):
        self.run_context(server=True)


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContextTests))
(output/'context-runtime.json').write_text(json.dumps({'tests':result.testsRun,
    'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)},indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
