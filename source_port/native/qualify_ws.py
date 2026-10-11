"""Original WS frame/static/dynamic integration. SPDX-License-Identifier: GPL-3.0-or-later."""
import gc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import weakref

spec = importlib.util.spec_from_file_location('_spell_analysis_qualification',
    next(Path('/out').glob('_spell_analysis_qualification*.so')))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

class Stop(BaseException): pass

class WarmFrame(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.source = Path(self.directory.name)/'procedure.py'
        self.stem = str(Path(self.directory.name)/'state')
        self.handles = []

    def tearDown(self):
        for handle in self.handles:
            native.ws_frame_event(handle,'close')
        self.handles.clear()
        self.directory.cleanup()

    def capture(self, source, line, *, save=False, occurrence=1, globals=None):
        self.source.write_text(source,encoding='utf-8')
        code = compile(source,str(self.source),'exec')
        namespace = {'__name__':'_qualified_procedure'} if globals is None else globals
        result = []
        visits = 0
        def tracing(frame,event,arg):
            nonlocal visits
            if frame.f_code.co_filename == str(self.source) and event == 'line' and frame.f_lineno == line:
                visits += 1
                if visits == occurrence:
                    handle=native.ws_frame_create(frame,str(self.source),self.stem if save else '')
                    self.handles.append(handle)
                    native.ws_frame_event(handle,'line')
                    if save: native.ws_frame_event(handle,'save')
                    result.append(handle)
                    raise Stop()
            return tracing
        previous=sys.gettrace()
        sys.settrace(tracing)
        try:
            with self.assertRaises(Stop): exec(code,namespace,namespace)
        finally: sys.settrace(previous)
        self.assertEqual(len(result),1)
        return result[0]

    def restored(self):
        handle=native.ws_frame_create(None,str(self.source),'',self.stem)
        self.handles.append(handle)
        return handle

    def test_module_resume_preserves_namespace_and_skips_prefix(self):
        handle=self.capture('value=7\nvalue+=3\nresult=value\n',3)
        state=native.ws_frame_state(handle)
        self.assertIs(state[1],state[2])
        native.ws_frame_event(handle,'fix')
        view=native.ws_frame_view(handle)
        self.assertEqual(view.f_lineno,3)
        self.assertEqual(native.ws_frame_resume(handle)[1]['result'],10)

    def test_function_locals_inspection_and_rebind_after_recovery(self):
        handle=self.capture('def work(x):\n value=x+1\n return value\nresult=work(9)\n',3)
        native.ws_frame_event(handle,'fix')
        view=native.ws_frame_view(handle)
        self.assertEqual(dict(view.f_locals),{'x':9,'value':10})
        self.assertEqual(view.f_lineno,3)
        events=[]
        def tracing(frame,event,arg):
            if frame.f_code.co_filename==str(self.source):
                events.append(event)
                if event=='call': native.ws_frame_rebind(handle,frame)
                if event=='line':
                    frame.f_locals['value']=42
                    native.ws_frame_event(handle,'line')
            return tracing
        sys.settrace(tracing)
        try: self.assertEqual(native.ws_frame_resume(handle)[0],42)
        finally: sys.settrace(None)
        self.assertEqual(events,['call','line','return'])
        self.assertEqual(native.ws_frame_state(handle)[2]['value'],42)

    def test_saved_loop_iterator_and_shared_global_function(self):
        handle=self.capture('value=7\ndef read(): return value\ntotal=0\nfor n in range(5):\n total+=n\nvalue=total\nresult=read()\n',5,save=True,occurrence=3)
        recovered=self.restored()
        self.assertEqual(native.ws_frame_resume(recovered)[1]['result'],10)

    def test_saved_handled_exception_and_finally(self):
        self.capture('events=[]\ntry:\n raise ValueError("saved")\nexcept ValueError:\n events.append("handler")\n try:\n  raise\n except ValueError as error:\n  events.append(str(error))\nfinally:\n events.append("finally")\n',5,save=True)
        self.assertEqual(native.ws_frame_resume(self.restored())[1]['events'],['handler','saved','finally'])
        self.assertIsNone(sys.exception())

    def test_failed_save_preserves_previous_complete_checkpoint(self):
        handle=self.capture('value=7\nresult=value\n',2,save=True)
        path=Path(self.stem+'_0.wsd')
        before=path.read_bytes()
        namespace=native.ws_frame_state(handle)[1]
        with self.source.open('rb') as stream:
            namespace['external_resource']=stream
            with self.assertRaisesRegex(RuntimeError,'resources'): native.ws_frame_event(handle,'save')
        del namespace['external_resource']
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(list(path.parent.glob(path.name+'.*')))
        self.assertEqual(native.ws_frame_resume(self.restored())[1]['result'],7)

    def test_source_identity_is_checked_before_deserialization(self):
        self.capture('value=7\nresult=value\n',2,save=True)
        self.source.write_text('value=0\nresult=value\n')
        with self.assertRaisesRegex(RuntimeError,'identity mismatch'): self.restored()

    def test_corrupt_and_truncated_checkpoint_fail(self):
        self.capture('value=7\nresult=value\n',2,save=True)
        path=Path(self.stem+'_0.wsd'); original=path.read_bytes()
        for bad in (original[:30],original[:-4],original[:-2]+b'X\n'):
            path.write_bytes(bad)
            with self.assertRaises(RuntimeError): self.restored()

    def test_invalid_state_replacement_preserves_previous_snapshot(self):
        handle=self.capture('value=7\nresult=value\n',2)
        state=native.ws_frame_state(handle)
        for invalid in (None,(),state[:-1]+(-1,),state[:5]+(b'invalid',)+state[6:]):
            with self.assertRaises(RuntimeError): native.ws_frame_set(handle,invalid)
            self.assertIs(native.ws_frame_state(handle),state)
        self.assertEqual(native.ws_frame_resume(handle)[1]['result'],7)

    def test_inspection_frame_cannot_be_updated_as_a_live_frame(self):
        handle=self.capture('value=7\nresult=value\n',2)
        native.ws_frame_event(handle,'fix')
        with self.assertRaisesRegex(RuntimeError,'inspection'): native.ws_frame_event(handle,'line')
        native.ws_frame_event(handle,'reset')
        with self.assertRaisesRegex(RuntimeError,'saved line'): native.ws_frame_event(handle,'fix')

    def test_repeated_frame_lifecycle_releases_code(self):
        refs=[]
        for _ in range(200):
            handle=self.capture('value=7\nresult=value\n',2)
            refs.append(weakref.ref(native.ws_frame_view(handle).f_code))
            native.ws_frame_event(handle,'fix')
            native.ws_frame_event(handle,'close')
            self.handles.remove(handle)
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_cleanup_removes_owned_checkpoint_files(self):
        handle=self.capture('value=7\nresult=value\n',2,save=True)
        self.assertTrue(Path(self.stem+'_0.wss').exists())
        self.assertTrue(Path(self.stem+'_0.wsd').exists())
        native.ws_frame_event(handle,'cleanup')
        self.assertFalse(list(Path(self.directory.name).glob('state*')))

    def test_persistent_recovery_in_fresh_process(self):
        self.capture('value=7\nvalue+=3\nresult=value\n',3,save=True)
        script='''import importlib.util,json,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('_spell_analysis_qualification',next(Path('/out').glob('_spell_analysis_qualification*.so')))
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
h=m.ws_frame_create(None,sys.argv[1],'',sys.argv[2])
result=m.ws_frame_resume(h)[1]['result']
m.ws_frame_event(h,'close')
print(json.dumps({'result':result}))
'''
        result=subprocess.run([sys.executable,'-I','-c',script,str(self.source),self.stem],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout),{'result':10})

result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WarmFrame))
Path('/out/ws-runtime.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),
    'errors':len(result.errors),'skips':len(result.skipped),'full_spell_warm_start_qualified':False,
    'address_sanitizer':True,'undefined_behavior_sanitizer':True,'leak_sanitizer':False},indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
