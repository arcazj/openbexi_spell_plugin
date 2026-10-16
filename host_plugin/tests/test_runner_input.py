"""Exercise the real runner stdin pipe with an independently controlled DAP peer.

Only Container is replaced: these tests claim console transport behavior, not
native SPELL execution. The peer records every request before responding.
"""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest


HOST_SOURCE = Path(__file__).resolve().parents[1] / 'src'

PEER = r'''
import json, os, queue, sys, threading, time, traceback
from pathlib import Path
from openbexi_spell_host.protocol import read, write

root=Path(sys.argv[1]); inbox=queue.Queue(); sequence=0; control=0
reject_answer=False; drop_answer=False
def record(value):
    with (root/'requests.jsonl').open('a',encoding='utf-8') as output:
        output.write(json.dumps(value)+'\n')
def receive():
    try:
        while (request:=read(sys.stdin.buffer)) is not None:
            inbox.put(request)
    finally:
        inbox.put(None)
def emit(message):
    global sequence
    sequence+=1
    write(sys.stdout.buffer,dict(seq=sequence,**message))
threading.Thread(target=receive,daemon=True).start()
try:
    while True:
        try:
            request=inbox.get(timeout=.01)
        except queue.Empty:
            request={}
        if request is None:
            break
        if request:
            record(request)
            command=request['command']
            if drop_answer and command=='spell/promptAnswer':
                break
            success=not (reject_answer and command=='spell/promptAnswer')
            emit(dict(type='response',request_seq=request['seq'],command=command,
                success=success,body={},message='' if success else 'Rejected controlled answer'))
            if command=='launch':
                emit(dict(type='event',event='initialized',body={}))
            elif command=='disconnect':
                break
        command_path=root/('control-%04d.json'%control)
        if command_path.exists():
            try:
                encoded=command_path.read_bytes()
            except PermissionError:
                # Windows can expose a rename before releasing its sharing
                # lock. Retry only this test-control file on the next poll.
                continue
            command=json.loads(encoded);control+=1
            if command.get('close'):
                break
            if command.get('reject_next_answer'):
                reject_answer=True
                continue
            if command.get('drop_next_answer'):
                drop_answer=True
                continue
            emit(command)
except BaseException:
    failure=traceback.format_exc()
    (root/'peer-error.txt').write_text(failure,encoding='utf-8')
    print(failure,file=sys.stderr,flush=True)
finally:
    # The controlled peer may still be reading its pipe. Avoid buffered-stdin
    # finalization races; every frame and journal line above is already flushed.
    os._exit(0)
'''

LAUNCHER = r'''
import subprocess,sys
from pathlib import Path
from openbexi_spell_host import runner

root=Path(sys.argv[1])
class OwnedPeer:
    def __init__(self,project,image):
        self.process=None
    def start(self,stderr):
        self.process=subprocess.Popen([sys.executable,'-u',str(root/'peer.py'),str(root)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr)
        return self.process
    def export(self):
        return root/'export'
    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
runner.Container=OwnedPeer
def record_reminder():
    with (root/'reminders.txt').open('a',encoding='utf-8') as output:
        output.write('reminder\n')
runner.reminder=record_reminder
raise SystemExit(runner.main(['--project',str(root),'--program',str(root/'procedure.py')]))
'''


class RunnerPipe:
    def __init__(self, root, managed=False):
        self.root, self.control = root, 0
        self.output, self.errors = [], []
        (root / 'peer.py').write_text(PEER, encoding='utf-8')
        (root / 'launcher.py').write_text(LAUNCHER, encoding='utf-8')
        (root / 'procedure.py').write_text('# Controlled transport fixture\n', encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(HOST_SOURCE), PYTHONIOENCODING='utf-8')
        env.pop('OPENBEXI_HOST_MANAGED', None)
        if managed:
            env['OPENBEXI_HOST_MANAGED'] = '1'
        self.process = subprocess.Popen([sys.executable, '-u', str(root / 'launcher.py'), str(root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', env=env)
        self.readers = []
        for stream, lines in ((self.process.stdout, self.output), (self.process.stderr, self.errors)):
            thread = threading.Thread(target=lambda source=stream, sink=lines: sink.extend(source), daemon=True)
            thread.start()
            self.readers.append(thread)
        self.wait(lambda: any(r['command'] == 'configurationDone' for r in self.requests()))

    def requests(self):
        path = self.root / 'requests.jsonl'
        if not path.exists():
            return []
        # A writer may be between write and flush; only complete records count.
        data = path.read_text(encoding='utf-8')
        complete = data.splitlines()
        if not data.endswith('\n'):
            complete = complete[:-1]
        return [json.loads(line) for line in complete]

    def answers(self):
        return [row['arguments'] for row in self.requests() if row['command'] == 'spell/promptAnswer']

    def wait(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            if self.process.poll() is not None:
                pytest.fail('Runner exited before observation: '+repr(self.errors))
            time.sleep(.01)
        pytest.fail('Runner observation timed out: '+repr(self.requests())+' '+repr(self.errors))

    def control_message(self, message):
        path = self.root / ('control-%04d.json' % self.control)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(message), encoding='utf-8')
        temporary.replace(path)
        self.control += 1

    def event(self, name, body=None):
        self.control_message(dict(type='event', event=name, body=body or {}))

    def input(self, text):
        self.process.stdin.write(text)
        self.process.stdin.flush()

    def prompt(self, identifier=None):
        body = {'ExpectedValues': 'accept,cancel'}
        if identifier is not None:
            body['promptId'] = identifier
        self.event('spell/prompt', body)

    def unchanged(self, count, seconds=.25):
        # A negative observation window is necessary: no request may leave the
        # wrapper merely because input arrived or an earlier prompt was answered.
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert len(self.answers()) == count, self.requests()
            assert not any(r['command'] == 'disconnect' for r in self.requests()), self.requests()
            assert self.process.poll() is None, self.errors
            time.sleep(.01)

    def finish(self):
        self.event('exited', {'exitCode': 0})
        self.event('terminated')
        assert self.process.wait(timeout=8) == 0, self.errors
        for reader in self.readers:
            reader.join(timeout=2)
        (self.root / 'runner-stdout.txt').write_text(''.join(self.output), encoding='utf-8')
        (self.root / 'runner-stderr.txt').write_text(''.join(self.errors), encoding='utf-8')
        assert sum(r['command'] == 'disconnect' for r in self.requests()) == 1

    def close(self):
        if self.process.poll() is None:
            self.event('exited', {'exitCode': 0})
            self.event('terminated')
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if not stream.closed:
                stream.close()
        for reader in self.readers:
            reader.join(timeout=2)
        (self.root / 'runner-stdout.txt').write_text(''.join(self.output), encoding='utf-8')
        (self.root / 'runner-stderr.txt').write_text(''.join(self.errors), encoding='utf-8')


@pytest.fixture
def runner_pipe(tmp_path):
    peer = RunnerPipe(tmp_path)
    try:
        yield peer
    finally:
        peer.close()


def test_early_lines_wait_for_each_prompt_across_two_sequences(runner_pipe):
    peer = runner_pipe
    expected = []
    for offset, values in ((0, ('alpha', 'beta')), (2, ('gamma', 'delta'))):
        # Native prompt text is output before its actionable spell/prompt event.
        peer.event('output', {'output': 'Type two answers now:\n'})
        peer.input(values[0]+'\n'+values[1]+'\n')
        peer.unchanged(offset)
        for index, value in enumerate(values):
            identifier = 'prompt-'+str(offset+index)
            peer.prompt(identifier)
            expected.append({'value': value, 'promptId': identifier})
            peer.wait(lambda: len(peer.answers()) == len(expected))
            assert peer.answers() == expected
            peer.unchanged(len(expected))
    # An additional prompt cannot replay a previously consumed line.
    peer.prompt('late')
    peer.unchanged(4)
    peer.input('last\n')
    peer.wait(lambda: len(peer.answers()) == 5)
    assert peer.answers() == expected+[{'value': 'last', 'promptId': 'late'}]
    peer.finish()


def test_timeout_reminder_dispatch_does_not_answer_or_close_prompt(runner_pipe):
    peer=runner_pipe
    peer.prompt('remind-1')
    peer.event('openbexi/promptReminder',{'promptId':'remind-1','procedureId':'main#1'})
    path=peer.root/'reminders.txt'
    peer.wait(lambda:path.exists() and path.read_text()=='reminder\n')
    peer.unchanged(0)
    peer.input('operator\n')
    peer.wait(lambda:len(peer.answers())==1)
    assert peer.answers()==[{'value':'operator','promptId':'remind-1'}]
    peer.finish()


def test_eof_after_piped_lines_drains_only_when_prompts_arrive(runner_pipe):
    peer = runner_pipe
    peer.input('first\nsecond\n')
    peer.process.stdin.close()
    peer.unchanged(0)
    for index, value in enumerate(('first', 'second'), 1):
        peer.prompt('pipe-'+str(index))
        peer.wait(lambda: len(peer.answers()) == index)
        assert peer.answers()[-1] == {'value': value, 'promptId': 'pipe-'+str(index)}
        peer.unchanged(index)
    peer.finish()


def test_ordinary_late_answer_without_prompt_id_is_sent_once(runner_pipe):
    peer = runner_pipe
    peer.prompt()
    peer.wait(lambda: any('SPELL choices' in line for line in peer.output))
    peer.unchanged(0)
    peer.input('ordinary\r\n')
    peer.wait(lambda: len(peer.answers()) == 1)
    assert peer.answers() == [{'value': 'ordinary'}]
    peer.unchanged(1)
    peer.finish()


def test_final_piped_line_without_newline_is_not_lost(runner_pipe):
    peer = runner_pipe
    peer.input('final answer')
    peer.process.stdin.close()
    peer.unchanged(0)
    peer.prompt('last-line')
    peer.wait(lambda: len(peer.answers()) == 1)
    assert peer.answers() == [{'value': 'final answer', 'promptId': 'last-line'}]
    peer.finish()


def test_rejected_answer_stops_without_replay_or_sending_queued_next_line(runner_pipe):
    peer = runner_pipe
    peer.control_message({'reject_next_answer': True})
    peer.input('once\nnext\n')
    peer.unchanged(0)
    peer.prompt('rejected')
    assert peer.process.wait(timeout=8) == 1
    assert peer.answers() == [{'value': 'once', 'promptId': 'rejected'}]
    assert sum(r['command'] == 'disconnect' for r in peer.requests()) == 1


@pytest.mark.parametrize('payload', ['x\n'*129, ('x'*4096+'\n')*65], ids=['line-limit', 'byte-limit'])
def test_early_input_queue_limits_fail_without_sending_any_answer(runner_pipe, payload):
    peer = runner_pipe
    peer.input(payload)
    assert peer.process.wait(timeout=8) == 1
    for reader in peer.readers:
        reader.join(timeout=2)
    assert 'Pending prompt input exceeds 128 lines or 256 KiB' in ''.join(peer.errors)
    assert peer.answers() == []
    assert sum(r['command'] == 'disconnect' for r in peer.requests()) == 1


def test_128_early_lines_are_permitted_but_not_sent_without_prompt(runner_pipe):
    peer = runner_pipe
    peer.input('x\n'*128)
    peer.unchanged(0)
    peer.finish()


def test_256_kib_of_early_lines_is_the_permitted_byte_boundary(runner_pipe):
    peer = runner_pipe
    peer.input(('x'*4096+'\n')*64)
    peer.unchanged(0)
    peer.finish()


def test_uncertain_answer_transport_does_not_replay_next_queued_line(runner_pipe):
    peer = runner_pipe
    peer.control_message({'drop_next_answer': True})
    peer.input('once\nnext\n')
    peer.unchanged(0)
    peer.prompt('transport-dropped')
    assert peer.process.wait(timeout=8) == 1
    assert peer.answers() == [{'value': 'once', 'promptId': 'transport-dropped'}]


def test_managed_stdin_eof_stops_instead_of_draining_early_answers(tmp_path):
    peer = RunnerPipe(tmp_path, managed=True)
    try:
        peer.input('queued\n')
        peer.process.stdin.close()
        assert peer.process.wait(timeout=8) == 130
        assert peer.answers() == []
        assert sum(r['command'] == 'disconnect' for r in peer.requests()) == 1
    finally:
        peer.close()


@pytest.mark.parametrize('payload,close_input', [(b'\xff\n', False), (b'\xc3', True)],
                         ids=['complete-line', 'partial-at-eof'])
def test_malformed_utf8_exits_promptly_without_answer(runner_pipe, payload, close_input):
    peer = runner_pipe
    peer.prompt('invalid-encoding')
    peer.wait(lambda: any('SPELL choices' in line for line in peer.output))
    peer.process.stdin.buffer.write(payload)
    peer.process.stdin.buffer.flush()
    if close_input:
        peer.process.stdin.close()
    assert peer.process.wait(timeout=8) == 1
    for reader in peer.readers:
        reader.join(timeout=2)
    assert "'utf-8' codec can't decode" in ''.join(peer.errors)
    assert peer.answers() == []
    assert sum(r['command'] == 'disconnect' for r in peer.requests()) == 1


@pytest.mark.parametrize('ending', [b'\n', b'\r\n'], ids=['lf', 'crlf'])
def test_64_kib_limit_is_per_line_after_a_short_prefix(runner_pipe, ending):
    peer = runner_pipe
    values = ['s'*100, 'x'*65536, 'tail']
    peer.process.stdin.buffer.write(ending.join(value.encode() for value in values)+ending)
    peer.process.stdin.buffer.flush()
    peer.unchanged(0)
    for index, expected in enumerate(values, 1):
        peer.prompt('line-'+str(index))
        peer.wait(lambda: len(peer.answers()) == index)
        answer = peer.answers()[-1]
        assert answer['promptId'] == 'line-'+str(index)
        assert len(answer['value']) == len(expected)
        assert hashlib.sha256(answer['value'].encode()).digest() == hashlib.sha256(expected.encode()).digest()
    peer.finish()


def test_a_line_over_64_kib_is_rejected_without_answer(runner_pipe):
    peer = runner_pipe
    peer.input('x'*65537+'\n')
    assert peer.process.wait(timeout=8) == 1
    for reader in peer.readers:
        reader.join(timeout=2)
    assert '64 KiB' in ''.join(peer.errors)
    assert peer.answers() == []
