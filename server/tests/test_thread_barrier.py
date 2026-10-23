"""Real CPython threads/monitoring and local wire; no family-pause claim."""

import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "host_runtime/python"

PRELUDE = """
import json,os,socket,sys,tempfile,threading,time,uuid
from pathlib import Path
sys.path.insert(0, MODULE)
from thread_barrier import ThreadBarrier,provider_call
temp=tempfile.TemporaryDirectory()
root=Path(temp.name)
entry=root/'procedure.py'
entry.write_text('')
gate=ThreadBarrier(root,entry)
scope={'counter':0,'ready':threading.Event()}
def execute(body):
    exec(compile(body,str(entry),'exec'),scope)
def until(test):
    deadline=time.monotonic()+2
    while not test():
        assert time.monotonic()<deadline,'Real participant did not reach expected state'
        time.sleep(.005)
barrier=str(uuid.uuid4())
"""


def scenario(code):
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "MODULE=" + repr(str(MODULE)) + "\n" + PRELUDE + textwrap.dedent(code),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_real_threads_hold_before_next_line_and_late_thread_cannot_enter():
    result = scenario('''
        execute("""import threading,time
        def background():
            global counter
            while True:
                counter+=1
                time.sleep(.002)
        for _ in range(2):
            threading.Thread(target=background,daemon=True).start()
        """)
        until(lambda:scope['counter']>5)
        answer=gate.pause(barrier)
        assert answer['observed_threads_held'] and answer['acknowledged_background_threads']==2
        before=scope['counter']
        threading.Thread(target=scope['background'],daemon=True).start()
        until(lambda:gate.snapshot_for(barrier)['acknowledged_background_threads']==3)
        time.sleep(.1)
        assert scope['counter']==before
        original=gate.deadline
        assert gate.pause(barrier)['observed_threads_held'] and gate.deadline==original
        try:gate.pause(str(uuid.uuid4()))
        except ValueError:pass
        else:raise AssertionError('Changed barrier identity was accepted')
        assert not answer['quiescence_proven'] and not answer['children_qualified']
        print(json.dumps(dict(held=3,counter_unchanged=True,full_family=False)))
    ''')
    assert result == dict(held=3, counter_unchanged=True, full_family=False)


def test_thread_blocked_in_c_times_out_and_late_ack_does_not_clear_expiry():
    result = scenario('''
        execute("""import threading,time
        def background():
            global counter
            ready.set()
            time.sleep(.5)
            counter+=1
        threading.Thread(target=background,daemon=True).start()
        """)
        assert scope['ready'].wait(1)
        started=time.monotonic()
        answer=gate.pause(barrier,timeout=.03)
        assert time.monotonic()-started<.2
        assert not answer['observed_threads_held'] and answer['deadline_expired']
        until(lambda:gate.snapshot_for(barrier)['acknowledged_background_threads']==1)
        late=gate.pause(barrier)
        assert not late['observed_threads_held'] and late['deadline_expired']
        assert scope['counter']==0
        print(json.dumps(dict(expired=True,late_ack_held=True,automatic_release=False)))
    ''')
    assert result["expired"] and not result["automatic_release"]


def test_disappeared_participant_cannot_be_synthesized_as_acknowledged():
    result = scenario('''
        execute("""import threading
        def background():
            ready.set()
        t=threading.Thread(target=background,daemon=True)
        t.start()
        """)
        scope['t'].join(1)
        assert not scope['t'].is_alive()
        answer=gate.pause(barrier,timeout=.02)
        assert answer['observed_background_threads']==1
        assert answer['acknowledged_background_threads']==0 and not answer['observed_threads_held']
        print(json.dumps(dict(disappeared_retained=True)))
    ''')
    assert result["disappeared_retained"]


def test_loopback_binding_replay_and_invalid_resume_do_not_release_real_thread():
    result = scenario('''
        execute("""import threading,time
        def background():
            global counter
            while True:
                counter+=1
                time.sleep(.002)
        threading.Thread(target=background,daemon=True).start()
        """)
        until(lambda:scope['counter']>2)
        gate.serve(0)
        assert gate.server.getsockname()[0]=='127.0.0.1'
        endpoint=gate.server.getsockname()[1]
        answer=provider_call(endpoint,barrier)
        assert answer['observed_threads_held']
        before=scope['counter']
        for request in [dict(action='resume',barrier_id=barrier),dict(action='pause',barrier_id=str(uuid.uuid4())),dict(action='snapshot',barrier_id=barrier,extra=True)]:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.settimeout(1);s.connect(('127.0.0.1',endpoint))
                s.sendall(json.dumps(request).encode()+b'\\n')
                assert json.loads(s.recv(2048))==dict(error='provider_request_denied')
        assert provider_call(endpoint,barrier)['observed_threads_held']
        time.sleep(.1)
        assert scope['counter']==before
        print(json.dumps(dict(replay_safe=True,resume_denied=True,counter_unchanged=True)))
    ''')
    assert result["replay_safe"] and result["resume_denied"]


def test_monitoring_tool_changes_are_unqualified_and_do_not_release_held_thread():
    result = scenario('''
        execute("""import threading,time
        def background():
            global counter
            while True:
                counter+=1
                time.sleep(.002)
        threading.Thread(target=background,daemon=True).start()
        """)
        until(lambda:scope['counter']>2)
        assert gate.pause(barrier)['observed_threads_held']
        before=scope['counter']
        sys.monitoring.set_events(gate.TOOL,0)
        answer=gate.snapshot_for(barrier)
        assert answer['failure']=='monitoring_configuration_changed'
        assert not answer['observed_threads_held']
        time.sleep(.05)
        assert scope['counter']==before
        print(json.dumps(dict(configuration_fenced=True,held=True)))
    ''')
    assert result["configuration_fenced"] and result["held"]


def test_monitoring_and_existing_native_style_trace_coexist():
    result = scenario("""
        calls=[]
        def trace(frame,event,arg):
            if frame.f_code.co_filename==str(entry):calls.append(event)
            return trace
        sys.settrace(trace)
        execute('RESULT=42\\nassert RESULT==42\\n')
        assert sys.gettrace() is trace and calls
        assert gate.main is threading.current_thread()
        assert not gate.pause(barrier,timeout=.01)['observed_threads_held']
        sys.settrace(None)
        print(json.dumps(dict(legacy_trace_preserved=True,no_empty_proof=True)))
    """)
    assert result["legacy_trace_preserved"] and result["no_empty_proof"]


@pytest.mark.parametrize("timeout", [0, -1, 4, True])
def test_unbounded_or_invalid_waits_are_rejected(timeout):
    result = scenario(f"""
        try:gate.pause(barrier,timeout={timeout!r})
        except ValueError:pass
        else:raise AssertionError('Invalid deadline admitted')
        assert gate.barrier_id is None
        print(json.dumps(dict(rejected=True)))
    """)
    assert result["rejected"]


def test_occupied_monitoring_slot_is_not_replaced():
    result = scenario("""
        try:ThreadBarrier(root,entry)
        except ValueError:pass
        else:raise AssertionError('Monitoring slot was replaced')
        assert sys.monitoring.get_tool(3)==gate.NAME
        print(json.dumps(dict(slot_preserved=True)))
    """)
    assert result["slot_preserved"]
