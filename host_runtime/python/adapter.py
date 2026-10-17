"""Debug Adapter Protocol host for the original native SPELL controller.

The container owns one Development session; no IPC ports are published.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import dis
from pathlib import Path
import queue
import re
import selectors
import signal
import sys
import threading
import time
import tokenize
import types

# -I intentionally excludes cwd; only the installed adapter directory is added.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native import NativeSession
from children import ChildProcedures
from prompts import PromptQueue


def read_messages(stream, incoming, stop, control=None):
    selector = selectors.DefaultSelector()
    selector.register(stream.fileno(), selectors.EVENT_READ)
    data = bytearray()
    length = None
    try:
        while not stop.is_set():
            if not selector.select(.1):
                continue
            chunk = os.read(stream.fileno(), 65536)
            if not chunk:
                if data or length is not None:
                    raise ValueError('Incomplete DAP message')
                incoming.put_nowait(None)
                return
            data.extend(chunk)
            while not stop.is_set():
                if length is None:
                    boundary = data.find(b'\r\n\r\n')
                    if boundary < 0:
                        if len(data) > 8192:
                            raise ValueError('DAP headers exceed 8 KiB')
                        break
                    if boundary > 8192:
                        raise ValueError('DAP headers exceed 8 KiB')
                    header = bytes(data[:boundary]).decode('ascii')
                    del data[:boundary + 4]
                    for line in header.split('\r\n'):
                        key, value = line.split(':', 1)
                        if key.lower() == 'content-length':
                            if length is not None:
                                raise ValueError('Duplicate DAP length')
                            length = int(value)
                    if length is None or not 0 < length <= 4 * 1024 * 1024:
                        raise ValueError('Invalid DAP length')
                if len(data) < length:
                    break
                message = json.loads(data[:length])
                del data[:length]
                length = None
                if control and control(message):
                    continue
                while not stop.is_set():
                    try:
                        incoming.put(message, timeout=.1)
                        break
                    except queue.Full:
                        continue
    except Exception as error:
        while not stop.is_set():
            try:
                incoming.put(error, timeout=.1)
                break
            except queue.Full:
                continue
    finally:
        selector.close()


class Adapter:
    def __init__(self):
        self.sequence = 0
        self.session = None
        self.configured = False
        self.done = False
        self.no_debug = False
        self.stop_on_entry = False
        self.last_status = None
        self.await_running = False
        self.status = {}
        self.notified_status = None
        self.status_revision = 0
        self.terminal_wait = None
        self.breakpoints = {}
        self.host_root = ''
        self.emit_lock = threading.Lock()
        self.driver_relay = None
        self.demo_dss = None
        self.runtime_root = Path(os.environ.get('OPENBEXI_SPELL_WORKSPACE', '/workspace')).resolve()
        self.watchdog_enabled = False
        self.last_heartbeat = time.monotonic()
        self.freeze_expected = False
        self.children = None
        self.prompts = None

    def control(self,message):
        if message.get('type') == 'event' and message.get('event') == 'openbexi/heartbeat':
            self.last_heartbeat = time.monotonic()
            return True
        if message.get('type') == 'request' and message.get('command') == 'openbexi/driverReply':
            try:
                if not self.driver_relay:
                    raise ValueError('No private driver relay')
                self.driver_relay.reply(message.get('arguments',{}))
                self.response(message)
            except Exception as error:
                self.response(message,error=error)
            return True
        return False

    def watchdog(self,stop):
        previous = time.monotonic()
        while not stop.wait(.2):
            now = time.monotonic()
            # Docker freezes this monitor together with all user descendants.
            # One declared freeze permits one bounded grace period on thaw.
            if self.freeze_expected and now - previous > 1:
                self.freeze_expected = False
                self.last_heartbeat = now
            previous = now
            if self.watchdog_enabled and now - self.last_heartbeat > 4:
                os._exit(75)  # Container init then tears down all descendants.

    def emit(self, message):
        with self.emit_lock:
            self.sequence += 1
            message['seq'] = self.sequence
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            sys.stdout.buffer.write(f'Content-Length: {len(data)}\r\n\r\n'.encode() + data)
            sys.stdout.buffer.flush()

    def event(self, event, **body):
        self.emit({'type': 'event', 'event': event, 'body': body})

    def response(self, request, body=None, error=None):
        self.emit({'type': 'response', 'request_seq': request['seq'],
            'command': request['command'], 'success': error is None,
            'body': body or {}, **({'message': str(error)} if error else {})})

    def source(self, procedure):
        relative = procedure + '.py'
        return {'name': relative.rsplit('/', 1)[-1],
                'path': self.host_root.rstrip('/\\') + '/' + relative}

    def present_child(self, instance):
        """Show visible child source in the client console beside the parent."""
        procedure = instance.rsplit('#', 1)[0]
        project = self.session.project.resolve()
        path = (project / (procedure + '.py')).resolve()
        if not path.is_relative_to(project):
            raise ValueError('Child source is outside the launched project')
        try:
            with tokenize.open(path) as stream:
                content = stream.read()
        except (OSError, UnicodeError, SyntaxError) as error:
            self.event('output', category='stderr', output=f'Child source unavailable: {instance}: {error}\n')
            return
        self.event('output', category='console', source=self.source(procedure), line=1,
                   output=f'=== SPELL child {instance} ===\n')
        # Keep every protocol message bounded without truncating the source.
        for offset in range(0, len(content), 16384):
            self.event('output', category='console', source=self.source(procedure),
                       output=content[offset:offset+16384])
        self.event('output', category='console', source=self.source(procedure),
                   output=('' if content.endswith('\n') else '\n')+'=== End child source ===\n')

    def relative(self, path):
        normalized = path.replace('\\', '/')
        root = self.host_root.replace('\\', '/').rstrip('/') + '/'
        if not normalized.startswith(root):
            raise ValueError('Breakpoint source is outside the launched project')
        relative = normalized[len(root):]
        if '..' in relative.split('/') or not relative.endswith('.py'):
            raise ValueError('Invalid breakpoint source')
        return relative[:-3]

    def dispatch(self, request):
        command = request['command']
        args = request.get('arguments', {})
        body = {}
        if command == 'initialize':
            self.watchdog_enabled = args.get('privateWatchdog') is True
            self.last_heartbeat = time.monotonic()
            body = {'supportsConfigurationDoneRequest': True,
                'supportsSetVariable': True, 'supportsTerminateRequest': True,
                'supportsEvaluateForHovers': False,
                'exceptionBreakpointFilters': []}
        elif command == 'openbexi/freezeWatchdog':
            self.freeze_expected = True
        elif command == 'launch':
            if self.session:
                raise ValueError('This adapter already owns a session')
            self.host_root = args['project']
            program = args['program'].replace('\\', '/')
            relative = self.relative(program) + '.py'
            supplied = args.get('args', [])
            if not isinstance(supplied, list) or len(supplied) > 1:
                raise ValueError('SPELL accepts one JSON object argument for native ARGS')
            native_arguments = args.get('spellArguments', json.loads(supplied[0]) if supplied else {})
            if args.get('driverRelay'):
                from openbexi_spell_dss.relay import Relay
                self.driver_relay = Relay(self.event)
            runtime_root = '/release' if args.get('immutableRelease') else str(self.runtime_root)
            if os.environ.get('OPENBEXI_SPELL_DEMO_DSS') == '1':
                if self.driver_relay or args.get('immutableRelease'):
                    raise ValueError('The learning simulator is available only in local Development')
                from demo_dss import DemoDss
                self.demo_dss = DemoDss(runtime_root, relative, native_arguments.get('LAB_MODE', 'Development'))
            self.session = NativeSession(runtime_root, runtime_root + '/' + relative, native_arguments,
                driver_port=(self.driver_relay.port if self.driver_relay else
                             self.demo_dss.port if self.demo_dss else None))
            self.no_debug = bool(args.get('noDebug'))
            self.stop_on_entry = bool(args.get('stopOnEntry'))
            try:
                self.session.start()
            except Exception:
                session, self.session = self.session, None
                session.close()
                raise
            self.session.pump = self.drain_events
            self.children = ChildProcedures(self.session.instance, self.present_child)
            self.prompts = PromptQueue(self.session.instance)
            self.response(request)
            self.event('initialized')
            return
        elif command == 'openbexi/driverReply':
            if not self.driver_relay:
                raise ValueError('No private driver relay')
            self.driver_relay.reply(args)
        elif command in {'disconnect', 'terminate'}:
            if self.session:
                self.session.close()
                self.session = None
            self.response(request)
            self.done = True
            return
        elif not self.session:
            raise ValueError('Launch a native session first')
        elif command == 'setBreakpoints':
            procedure = self.relative(args['source']['path'])
            entries = args.get('breakpoints', [])
            if any('condition' in item or 'hitCondition' in item or 'logMessage' in item for item in entries):
                raise ValueError('Conditional breakpoints and logpoints are not supported')
            lines = [item['line'] for item in entries]
            if any(type(line) is not int or line < 1 for line in lines):
                raise ValueError('Breakpoint lines must be positive integers')
            source = self.session.project / (procedure + '.py')
            valid = set()
            if source.is_file() and source.resolve().is_relative_to(self.session.project):
                def collect(code):
                    valid.update(line for _, line in dis.findlinestarts(code) if line > 0)
                    for value in code.co_consts:
                        if isinstance(value, types.CodeType):
                            collect(value)
                collect(compile(source.read_bytes(), str(source), 'exec'))
            self.breakpoints[procedure] = [line for line in lines if line in valid]
            self.session.request('REQ_CLEAR_BREAKPOINT')
            for name, values in self.breakpoints.items():
                for line in values:
                    self.session.request('REQ_SET_BREAKPOINT', {'BreakpointProc': name,
                        'BreakpointLine': str(line), 'BreakpointType': 'PERMANENT'})
            body = {'breakpoints': [{'verified': line in valid, 'line': line,
                **({} if line in valid else {'message': 'No executable line in the run snapshot'})}
                for line in lines]}
        elif command == 'setExceptionBreakpoints':
            body = {'breakpoints': []}
        elif command == 'configurationDone':
            self.configured = True
            if self.stop_on_entry and not self.no_debug:
                self.status = self.session.request('REQ_EXEC_STATUS')
                self.last_status = 'PAUSED'
                self.response(request)
                self.event('stopped', reason='entry', threadId=1, allThreadsStopped=True)
                return
            self.await_running = True
            self.session.request('CMD_RUN', send=True)
        elif command == 'threads':
            body = {'threads': [{'id': 1, 'name': 'SPELL procedure'}]}
        elif command == 'stackTrace':
            self.require_paused()
            self.status = self.session.request('REQ_EXEC_STATUS')
            frames = []
            # Original SPELLcallstack joins each procedure:line with ':'.
            # '/' belongs to a procedure's relative project path.
            positions = re.findall(r'([^:]+):(\d+)(?=:|$)', self.status.get('Csp', ''))
            for index, (procedure, line) in enumerate(reversed(positions)):
                frames.append({'id': index + 1, 'name': procedure,
                    'source': self.source(procedure), 'line': int(line), 'column': 1})
            body = {'stackFrames': frames, 'totalFrames': len(frames)}
        elif command == 'scopes':
            self.require_paused()
            if args['frameId'] != 1:
                body = {'scopes': []}  # Upstream exposes current-frame locals only.
            else:
                body = {'scopes': [{'name': 'Current frame', 'variablesReference': 1, 'expensive': False}]}
        elif command == 'variables':
            self.require_paused()
            if args['variablesReference'] != 1:
                raise ValueError('Unknown variable reference')
            fields = self.session.request('REQ_GET_VARIABLES')
            names = fields.get('VarName', '').split('\4')
            values = fields.get('VarValue', '').split('\4')
            type_names = fields.get('VarType', '').split('\4')
            body = {'variables': [{'name': name, 'value': value, 'type': kind,
                'variablesReference': 0} for name, value, kind in zip(names, values, type_names) if name]}
        elif command == 'setVariable':
            self.require_paused()
            if args['variablesReference'] != 1:
                raise ValueError('Unknown variable reference')
            fields = self.session.request('REQ_GET_VARIABLES')
            scopes = dict(zip(fields.get('VarName', '').split('\4'), fields.get('VarGlobal', '').split('\4')))
            if args['name'] not in scopes:
                raise ValueError('Unknown variable')
            self.session.request('REQ_CHANGE_VARIABLE', {'VarName': args['name'],
                'VarValue': args['value'], 'VarGlobal': scopes[args['name']]})
            fields = self.session.request('REQ_GET_VARIABLES')
            values = dict(zip(fields.get('VarName', '').split('\4'), fields.get('VarValue', '').split('\4')))
            body = {'value': values[args['name']], 'variablesReference': 0}
        elif command in {'continue', 'next', 'stepIn', 'pause'}:
            if command != 'pause':
                self.require_paused()
            native = {'continue': 'CMD_RUN', 'next': 'CMD_STEP_OVER',
                      'stepIn': 'CMD_STEP', 'pause': 'CMD_PAUSE'}[command]
            self.await_running = command != 'pause'
            self.session.request(native, send=True)
            self.last_status = 'RUNNING' if command != 'pause' else self.last_status
            self.response(request, {'allThreadsContinued': True} if command == 'continue' else {})
            if command != 'pause':
                self.event('continued', threadId=1, allThreadsContinued=True)
            return
        elif command in {'spell/promptAnswer', 'openbexi/input'}:
            self.answer_prompt(request, args)
            return
        else:
            raise ValueError('Unsupported native debugger request: ' + command)
        self.response(request, body)

    def expose_prompt(self, repeat=False):
        if not self.prompts:
            return
        prompt = self.prompts.expose(repeat)
        if prompt is None:
            return
        fields = dict(prompt.fields, promptId=prompt.identifier, procedureId=prompt.procedure)
        self.event('spell/prompt', **fields)
        self.event('openbexi/inputRequest', text=fields.get('Text', ''),
                   choices=fields.get('ExpectedValues', ''), answerFormat='native option index',
                   promptId=prompt.identifier, procedureId=prompt.procedure)
        self.event('output', category='console', output='SPELL prompt: ' + fields.get('Text', '') + '\n')

    def answer_prompt(self, request, args):
        prompt = None
        try:
            if not self.prompts:
                raise ValueError('No active native prompt accepts an answer')
            prompt = self.prompts.begin(args.get('promptId'))
            value = args['text'] if request['command'] == 'openbexi/input' else args['value']
            status = self.session.request('REQ_EXEC_STATUS', procedure=prompt.procedure)
            if status.get('ExecutorStatus') != 'PROMPT':
                self.prompts.invalidate(prompt.procedure)
                raise ValueError('The native procedure is not waiting for a prompt answer')
            self.prompts.before_send(prompt)
            self.session.request('MSG_ANSWER', {'ReturnValue': str(value)}, send=True,
                                 procedure=prompt.procedure)
            self.prompts.complete(prompt)
        except Exception as error:
            if prompt and self.prompts.answering is prompt:
                self.prompts.cancel(prompt)
            self.response(request, error=error)
            if self.prompts and not self.prompts.failure:
                self.expose_prompt(repeat=True)
            return
        self.response(request)
        # Preserve response/event order for clients that clear their input state
        # when submitting an answer. Withheld prompts become visible only now.
        self.expose_prompt()

    def require_paused(self):
        self.status = self.session.request('REQ_EXEC_STATUS')
        if self.status.get('ExecutorStatus') != 'PAUSED':
            raise ValueError('Native procedure is not paused')

    def drain_events(self):
        if not self.session:
            return
        for _ in range(128):
            try:
                item = self.session.events.get_nowait()
            except queue.Empty:
                break
            message = item.get('message', {})
            fields = message.get('fields', {})
            if self.children:
                self.children.observe(message)
            if self.prompts:
                self.prompts.observe(message, self.children.children if self.children else ())
            if fields.get('DataType') == 'STATUS' and fields.get('ProcId') == self.session.instance:
                self.status_revision += 1
                self.notified_status = fields.get('ExecutorStatus')
                if self.notified_status == 'RUNNING':
                    self.await_running = False
            if message.get('id') == 'MSG_WRITE':
                self.event('output', category='stdout', output=fields.get('Text', '') + '\n')
            elif item.get('event') == 'connectionError':
                raise RuntimeError(item.get('error', 'Native connection failed'))
        self.expose_prompt()

    def poll(self):
        if not self.session:
            return
        self.drain_events()
        if not self.configured:
            return
        if self.children:
            self.children.service(self.session)
        revision = self.status_revision
        self.status = self.session.request('REQ_EXEC_STATUS')
        # Notifications can arrive while the synchronous status reply is in
        # flight. Forward them before closing a completed native session.
        self.drain_events()
        if self.status_revision != revision:
            # The reply may describe the state before a notification consumed
            # while waiting for it (notably the startup PAUSED -> RUNNING).
            # Query again after that transition before emitting stopped.
            return
        if self.prompts:
            for prompt in self.prompts.reminders():
                self.event('openbexi/promptReminder', promptId=prompt.identifier,
                           procedureId=prompt.procedure)
        status = self.status.get('ExecutorStatus')
        if self.await_running:
            return
        if status in {'FINISHED', 'ERROR', 'ABORTED'} and self.notified_status != status:
            # Status queries bypass the ordered GUI notification stream. Wait
            # for its terminal notification so preceding output is delivered.
            if self.terminal_wait is None:
                self.terminal_wait = time.monotonic()
            elif time.monotonic() - self.terminal_wait > 10:
                raise RuntimeError('Native terminal notification timed out')
            return
        if status != self.last_status:
            previous, self.last_status = self.last_status, status
            if status == 'PAUSED':
                self.event('stopped', reason='breakpoint', threadId=1, allThreadsStopped=True)
            elif status == 'ERROR':
                message = self.status.get('ErrorMsg', '')
                reason = self.status.get('ErrorReason', '')
                if reason and '\n' + reason + '\n' not in '\n' + message + '\n':
                    message = message + '\n' + reason if message else reason
                self.event('output', category='stderr', output=(message or str(self.status)) + '\n')
            if status in {'FINISHED', 'ERROR', 'ABORTED'}:
                exit_code = 0 if status == 'FINISHED' else 1
                self.session.close()
                self.session = None
                if self.demo_dss:
                    demo, self.demo_dss = self.demo_dss, None
                    demo.close()
                self.event('exited', exitCode=exit_code)
                self.event('terminated')


def main():
    adapter = Adapter()
    signal.signal(signal.SIGTERM, lambda *_: setattr(adapter, 'done', True))
    incoming = queue.Queue(maxsize=128)
    stop = threading.Event()
    reader = threading.Thread(target=read_messages, args=(sys.stdin.buffer, incoming, stop,adapter.control))
    reader.start()
    watchdog = threading.Thread(target=adapter.watchdog,args=(stop,),name='native-parent-watchdog')
    watchdog.start()
    try:
        while not adapter.done:
            try:
                message = incoming.get(timeout=.05)
            except queue.Empty:
                message = 'poll'
            if message is None:
                break
            if isinstance(message, Exception):
                raise message
            if message != 'poll':
                try:
                    adapter.dispatch(message)
                except Exception as error:
                    adapter.response(message, error=error)
            adapter.poll()
    except Exception as error:
        if adapter.session:
            session, adapter.session = adapter.session, None
            try:
                session.close()
            except Exception as cleanup_error:
                adapter.event('output', category='stderr', output=str(cleanup_error) + '\n')
        adapter.event('output', category='stderr', output=str(error) + '\n')
        adapter.event('exited', exitCode=1)
        adapter.event('terminated')
        return 1
    finally:
        stop.set()
        reader.join()
        watchdog.join()
        if adapter.session:
            adapter.session.close()
        if adapter.driver_relay:
            adapter.driver_relay.close()
        if adapter.demo_dss:
            adapter.demo_dss.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
