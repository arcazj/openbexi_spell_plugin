"""Owned local Development session using the installed original SPELL runtime."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
import queue
import re
import select
import signal
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET


class BridgeConnectionError(RuntimeError):
    """The initial IPC connection failed before any request was sent."""


class Bridge:
    """One owned IPC process with ordered notifications and single-flight RPC.

    Transport uncertainty permanently fences this instance. Reconnecting here
    must never become an implicit retry of an already sent native command.
    """

    MAX_FRAME = 4 * 1024 * 1024
    STARTUP_EVENTS = 256

    def __init__(self, port, environment, log, events, *, connect_timeout=10,
                 executable='/bridge/spell-host-ipc'):
        self._timeout(connect_timeout)
        # The queue identity never changes after the reader starts. A separate
        # bounded pre-handshake buffer is owned exclusively by the reader.
        self.events = events
        self.replies = queue.Queue(maxsize=2)
        self.closing = threading.Event()
        self.connected = threading.Event()
        self.failed = threading.Event()
        self.exchange_lock = threading.Lock()
        self.failure_lock = threading.Lock()
        self.failure = None
        self.sequence = 0
        self.process = subprocess.Popen([str(executable), str(port)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            text=True, encoding='utf-8', env=environment)
        os.set_blocking(self.process.stdin.fileno(), False)
        self.thread = threading.Thread(target=self.read, name='native-ipc-reader')
        self.thread.start()
        try:
            first = self.replies.get(timeout=connect_timeout)
        except queue.Empty:
            self.close()
            raise BridgeConnectionError('Native bridge connection timed out') from None
        if first.get('event') != 'connected' or self.failed.is_set():
            self.close()
            raise BridgeConnectionError('Native IPC could not connect')

    @staticmethod
    def _timeout(value):
        if type(value) not in (int, float) or not 0 < value <= 10:
            raise ValueError('Native bridge timeout must be finite and in (0, 10]')

    def _fail(self, reason, event=None):
        """Keep a failure latch even if the bounded event queue is full."""
        with self.failure_lock:
            if self.failed.is_set():
                return
            self.failure = reason
            self.failed.set()
        # A failed connection attempt must not poison the shared notification
        # queue used by a later, still pre-request connection attempt.
        if self.connected.is_set() and not self.closing.is_set():
            try:
                self.events.put_nowait(event or {'event': 'connectionError', 'error': reason})
            except queue.Full:
                pass  # Every request checks the independent failure latch.
        try:
            self.replies.put_nowait({'error': reason})
        except queue.Full:
            pass

    def _available(self):
        if self.closing.is_set() or self.failed.is_set():
            raise RuntimeError('Native bridge unavailable: ' + (self.failure or 'closed'))

    def read(self):
        pending = []
        try:
            while not self.closing.is_set():
                line = self.process.stdout.readline(self.MAX_FRAME + 1)
                if not line:
                    if not self.closing.is_set():
                        self._fail('Native bridge ended')
                    return
                if len(line.encode('utf-8')) > self.MAX_FRAME or not line.endswith('\n'):
                    raise ValueError('Native bridge frame exceeds bound')
                item = json.loads(line)
                if type(item) is not dict:
                    raise ValueError('Native bridge frame is not an object')
                if item.get('event') == 'connected':
                    if self.connected.is_set() or 'seq' in item:
                        raise ValueError('Duplicate native bridge handshake')
                    self.connected.set()
                    self.replies.put_nowait(item)
                    for buffered in pending:
                        self.publish(buffered)
                    pending.clear()
                elif not self.connected.is_set():
                    if 'seq' in item or item.get('event') in {'connectionError', 'connectionClosed'}:
                        raise ValueError('Native bridge connection failed')
                    if len(pending) >= self.STARTUP_EVENTS:
                        raise ValueError('Native bridge startup notification capacity')
                    pending.append(item)
                elif item.get('event') in {'connectionError', 'connectionClosed'}:
                    # Fence first: observing closure must never race a new write.
                    self._fail('Native IPC connection closed', item)
                    return
                elif 'seq' in item:
                    self.replies.put_nowait(item)
                else:
                    self.publish(item)
        except Exception:
            # No private JSON frame or procedure values in parser diagnostics.
            self._fail('Native bridge protocol failed')
        finally:
            if not self.closing.is_set() and not self.failed.is_set():
                self._fail('Native bridge ended')

    def publish(self, item):
        while not self.closing.is_set() and not self.failed.is_set():
            try:
                self.events.put(item, timeout=.1)
                return
            except queue.Full:
                continue

    def _write_packet(self, packet, deadline):
        fd = self.process.stdin.fileno()
        raw = packet.encode('utf-8')
        offset = 0
        while offset < len(raw):
            self._available()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Native bridge write deadline expired')
            _, ready, _ = select.select([], [fd], [], min(.05, remaining))
            if not ready:
                continue
            try:
                written = os.write(fd, raw[offset:])
            except BlockingIOError:
                continue
            if written <= 0:
                raise OSError('Native bridge pipe closed')
            offset += written

    def exchange(self, identifier, receiver, fields=None, *, send=False, pump=None, timeout=10):
        self._timeout(timeout)
        # Reentrancy from an event pump is also rejected before touching the
        # wire: two callers cannot swap each other's sequence or receipt.
        if not self.exchange_lock.acquire(blocking=False):
            raise RuntimeError('A native request is already in flight')
        attempted = settled = False
        try:
            self._available()
            if self.sequence >= 2**32 - 1:
                self._fail('Native bridge sequence exhausted')
                raise RuntimeError('Native bridge sequence exhausted')
            self.sequence += 1
            sequence = self.sequence
            packet = json.dumps({'seq': sequence,
                'operation': 'send' if send else 'request', 'id': identifier,
                'receiver': receiver, 'fields': fields or {}}) + '\n'
            if len(packet.encode('utf-8')) > self.MAX_FRAME:
                raise ValueError('Native bridge request exceeds bound')
            deadline = time.monotonic() + timeout
            attempted = True  # Any later interruption leaves a non-replayable attempt.
            try:
                self._write_packet(packet, deadline)
            except (OSError, ValueError):
                self._fail('Native bridge write uncertain')
                raise RuntimeError('Native bridge write uncertain') from None
            while True:
                self._available()
                # Notifications and replies share one pipe. Bounded pumps keep
                # a reply behind a normal notification burst reachable.
                if pump:
                    try:
                        pump()
                    except Exception:
                        self._fail('Native notification processing failed')
                        raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._fail('Native reply timed out')
                    raise RuntimeError(f'{identifier}: Native reply timed out')
                try:
                    reply = self.replies.get(timeout=min(.05, remaining))
                    break
                except queue.Empty:
                    continue
            self._available()
            if (type(reply.get('seq')) is not int or reply['seq'] != sequence
                    or type(reply.get('ok')) is not bool):
                self._fail('Native response identity differs')
                raise RuntimeError('Native response identity differs')
            # A negative bridge envelope is not necessarily a native rejection.
            # native_bridge.cpp also emits ok=false/error for exceptions and IPC
            # timeouts, without a native message. Such an outcome cannot permit
            # retransmission, even though its bridge sequence is correlated.
            if not reply['ok'] and ('error' in reply or 'message' not in reply):
                self._fail('Native IPC dispatch outcome uncertain')
                raise RuntimeError(f'{identifier}: Native IPC dispatch outcome uncertain')
            message = reply.get('message', {})
            if type(message) is not dict or type(message.get('fields', {})) is not dict:
                self._fail('Native response fields differ')
                raise RuntimeError('Native response fields differ')
            if not reply['ok']:
                # A native error *response* retains the original denial oracle.
                # This settles only the bridge exchange, not procedure effects.
                settled = True
                raise RuntimeError(f'{identifier}: {reply}')
            settled = True
            return message.get('fields', {})
        except BaseException:
            if attempted and not settled:
                self._fail('Native request interrupted or uncertain')
            raise
        finally:
            self.exchange_lock.release()

    def close(self):
        self.closing.set()
        self._fail('Native bridge closed')
        if self.process.stdin and not self.process.stdin.closed:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('Native bridge reader did not terminate')
        if self.process.stdout and not self.process.stdout.closed:
            self.process.stdout.close()

class StartupObservation:
    """Latest status for exactly the admitted root; never execution authority."""

    STATUSES = frozenset({
        'UNKNOWN', 'UNINIT', 'LOADED', 'RELOADING', 'RUNNING', 'PAUSED', 'WAITING',
        'PROMPT', 'INTERRUPTED', 'ERROR', 'ABORTED', 'FINISHED',
    })

    def __init__(self, instance):
        self.instance = instance
        self.status = None
        self.notifications = 0

    def drain(self, events):
        # Match the worker's bounded pump: a busy notification stream must
        # yield to the original command reply, without imposing a lifetime cap.
        for _ in range(64):
            try:
                item = events.get_nowait()
            except queue.Empty:
                return
            self.notifications += 1
            if type(item) is not dict:
                raise RuntimeError('Invalid native startup notification')
            if item.get('event') in {'connectionError', 'connectionClosed'}:
                raise RuntimeError('Native startup connection failed')
            message = item.get('message', {})
            if type(message) is not dict:
                raise RuntimeError('Invalid native startup message')
            fields = message.get('fields', {})
            if type(fields) is not dict:
                raise RuntimeError('Invalid native startup fields')
            if fields.get('DataType') != 'STATUS' or fields.get('ProcId') != self.instance:
                continue
            status = fields.get('ExecutorStatus')
            if type(status) is not str or status not in self.STATUSES:
                raise RuntimeError('Invalid native startup status')
            self.status = status
            if status in {'ERROR', 'ABORTED', 'FINISHED'}:
                raise RuntimeError('Native root became terminal during startup: ' + status)

    def paused(self, info):
        if type(info) is not dict:
            raise RuntimeError('Invalid native startup status response')
        if info.get('ProcId') != self.instance:
            raise RuntimeError('Native startup status response scope differs')
        status = info.get('ExecutorStatus')
        if type(status) is not str or status not in self.STATUSES:
            raise RuntimeError('Invalid native startup status response')
        if status in {'ERROR', 'ABORTED', 'FINISHED'}:
            raise RuntimeError('Native root became terminal during startup: ' + status)
        return status == 'PAUSED' and self.status == 'PAUSED'


class NativeSession:
    def __init__(self, project, script, arguments, *, driver_port=None, user_library=None,
                 native_home=None, admission_socket=None, consume_fence_probe=False,
                 owner_step_probe=False):
        self.driver_port = driver_port
        self.native_home = None
        self.admission_socket = admission_socket
        self.gui_binding_callback = None
        if native_home is not None:
            home = Path(native_home).resolve(strict=True)
            if not home.is_dir() or not os.statvfs(home).f_flag & os.ST_RDONLY or not admission_socket:
                raise ValueError('Native admission home must be an operator read-only mount')
            self.native_home = home
        elif admission_socket is not None:
            raise ValueError('Native admission socket requires the checked native home')
        if type(consume_fence_probe) is not bool or (consume_fence_probe and self.native_home is None):
            raise ValueError('Native consumption probe requires the checked candidate')
        self.consume_fence_probe = consume_fence_probe
        if type(owner_step_probe) is not bool or (owner_step_probe and (
                self.native_home is None or consume_fence_probe)):
            raise ValueError('Native owner probe requires its separate checked candidate')
        self.owner_step_probe = owner_step_probe
        self.user_library = None
        if user_library is not None:
            library = Path(user_library).resolve(strict=True)
            if not library.is_dir() or not os.statvfs(library).f_flag & os.ST_RDONLY:
                raise ValueError('Native user library must be an operator read-only mount')
            self.user_library = library
        self.project = Path(project).resolve()
        self.script = Path(script).resolve()
        if not self.project.is_dir() or not self.script.is_file() or self.script.suffix != '.py':
            raise ValueError('Select an existing Python procedure')
        if not self.script.is_relative_to(self.project):
            raise ValueError('Procedure must be within the selected project')
        if not isinstance(arguments, dict):
            raise ValueError('SPELL arguments must be a JSON object for native ARGS')
        self.arguments = repr(arguments)
        self.procedure = self.script.relative_to(self.project).with_suffix('').as_posix()
        self.instance = self.procedure + '#1'
        self.events = queue.Queue(maxsize=256)
        self.listener = self.context = self.process = self.log = None
        self.opened = False
        self.pump = None
        self.directory = tempfile.TemporaryDirectory(prefix='spell-host-')

    def connect_bridge(self, port, environment, deadline):
        while True:
            if self.process.poll() is not None:
                raise RuntimeError('Native listener exited during startup')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeConnectionError('Native IPC startup deadline expired')
            try:
                return Bridge(port, environment, self.log, self.events,
                              connect_timeout=min(10, remaining),
                              executable=(self.native_home / 'bin/spell-host-ipc'
                                          if self.native_home is not None
                                          else '/bridge/spell-host-ipc'))
            except BridgeConnectionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)

    def start(self):
        root = Path(self.directory.name)
        example = json.loads(subprocess.check_output(
            ['spell-native', 'init-example', str(root / 'session')], text=True))
        server = ET.parse(example['config'])
        ET.SubElement(server.getroot().find('context'), 'property', name='CheckSpacecraft').text = 'false'
        if self.native_home is not None:
            server.find("./context/property[@name='ExecutorProgram']").text = str(
                self.native_home / 'bin/SPELL-Executor')
        server.write(example['config'], encoding='utf-8')
        config = root / 'session/config/contexts/context_example.xml'
        tree = ET.parse(config)
        # The upstream resolver tokenizes '/' and expects an environment-rooted
        # path. A literal absolute path loses its leading separator there.
        tree.find('procpath').text = '$OPENBEXI_SPELL_PROJECT'
        if self.driver_port:
            tree.find('driver').text = 'openbexi_dss_proxy'
            driver = ET.parse(root / 'session/config/spell/driver_example.xml')
            driver.getroot().set('id','openbexi_dss_proxy')
            driver.find('interfaces').text = 'TM,TC,EV,PCS,MEM,RSC,TASK,RNG,USER,TIME'
            # The server's explicit driver-file inventory points to this file;
            # changing only its filename would leave the new driver unregistered.
            driver.write(root / 'session/config/spell/driver_example.xml',encoding='utf-8')
        # Keep the upstream UserLib directory separate. The original executor
        # auto-imports everything in libpath before procedure execution; using
        # the project there would run ordinary script bodies during startup.
        if self.user_library is not None:
            tree.find('libpath').text = '$OPENBEXI_SPELL_USER_LIBRARY'
        tree.write(config, encoding='utf-8')
        environment = dict(os.environ, **example['environment'], OPENBEXI_SPELL_PROJECT=str(self.project))
        if self.native_home is not None:
            # This role marker belongs to the candidate Executor's own main;
            # the native Listener/Context must retain their metadata graph.
            environment.pop('OPENBEXI_V08_EXECUTOR_BOOTSTRAP', None)
            environment.update(SPELL_HOME=str(self.native_home),
                OPENBEXI_V08_ADMISSION_SOCKET=str(self.admission_socket),
                OPENBEXI_V08_AGENT_PID=str(os.getpid()))
            if self.consume_fence_probe:
                environment['OPENBEXI_V08_CONSUMPTION_PROBE'] = '1'
            if self.owner_step_probe:
                environment['OPENBEXI_V08_OWNER_STEP_PROBE'] = '1'
        if self.user_library is not None:
            environment['OPENBEXI_SPELL_USER_LIBRARY'] = str(self.user_library)
            environment['OPENBEXI_SPELL_ENTRYPOINT'] = str(self.script)
        if os.environ.get('OPENBEXI_V08_RUNTIME_EPOCH'):
            environment['OPENBEXI_V08_RUNTIME_EPOCH'] = os.environ['OPENBEXI_V08_RUNTIME_EPOCH']
        if self.driver_port:
            environment['OPENBEXI_DRIVER_RELAY_PORT'] = str(self.driver_port)
        self.log = (root / 'native.log').open('w+')
        self.process = subprocess.Popen(['spell-native', 'listener', '-c', example['config']],
            cwd=self.project, env=environment, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True)
        startup = StartupObservation(self.instance)
        def pump():
            startup.drain(self.events)
        deadline = time.monotonic() + 10
        self.listener = self.connect_bridge(9980, environment, deadline)
        self.listener.exchange('REQ_GUI_LOGIN', 'LST',
            {'ContextName': 'example', 'Host': 'openbexi-host-v1', 'GuiMode': 'Development'}, pump=pump)
        while time.monotonic() < deadline:
            info = self.listener.exchange('REQ_CTX_INFO', 'LST', {'ContextName': 'example'}, pump=pump)
            if info.get('ContextStatus') == 'RUNNING':
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Native context startup timed out')
        # RUNNING is listener bookkeeping; the context IPC accept thread can
        # still be starting. Retry only connection setup, never a sent request.
        self.context = self.connect_bridge(int(info['ContextPort']), environment, deadline)
        if self.native_home is not None:
            if self.gui_binding_callback is None:
                raise RuntimeError('Native GUI admission provider unavailable')
            key = self.context.exchange('REQ_V08_GUI_KEY', 'CTX', pump=pump)['GuiKey']
            self.gui_binding_callback(int(key), self.context.process)
        self.context.exchange('REQ_GUI_LOGIN', 'CTX', {'Host': 'openbexi-host-v1'}, pump=pump)
        self.request('REQ_OPEN_EXEC', context=True, fields={'GuiMode': 'CONTROL',
            'Arguments': self.arguments, 'OpenMode': '{Automatic:True,Visible:True,Blocking:False}'}, pump=pump)
        self.opened = True
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            pump()
            info = self.request('REQ_EXEC_INFO', context=True, pump=pump)
            # A synchronous reply can be read while preceding notifications
            # still occupy the queue. Do not declare readiness from a stale
            # PAUSED observation before the bounded pump catches up.
            pump()
            if self.events.empty() and startup.paused(info):
                return
            time.sleep(.05)
        status = info.get('ExecutorStatus')
        status = status if type(status) is str and status in StartupObservation.STATUSES else 'UNKNOWN'
        raise RuntimeError('Native procedure startup timed out: status=' + status +
                           '; notified_status=' + str(startup.status) +
                           '; notifications=' + str(startup.notifications))

    def request(self, identifier, fields=None, *, context=False, send=False, procedure=None, pump=None):
        target = self.instance if procedure is None else procedure
        return self.context.exchange(identifier, 'CTX' if context else target,
            dict(fields or {}, ProcId=target), send=send, pump=self.pump if pump is None else pump)

    def close(self):
        errors = []
        if self.context:
            try:
                if self.opened and self.native_home is None:
                    self.request('REQ_CLOSE_EXEC', context=True)
                if self.native_home is None:
                    self.context.exchange('REQ_GUI_LOGOUT', 'CTX')
            except Exception as error:
                errors.append(str(error))
            try:
                self.context.close()
            except Exception as error:
                errors.append(str(error))
            self.context = None
        if self.listener:
            try:
                if self.native_home is None:
                    self.listener.exchange('REQ_CLOSE_CTX', 'LST', {'ContextName': 'example'})
                    self.listener.exchange('REQ_GUI_LOGOUT', 'LST')
            except Exception as error:
                errors.append(str(error))
            try:
                self.listener.close()
            except Exception as error:
                errors.append(str(error))
            self.listener = None
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                errors.append('Native listener required forced shutdown')
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=5)
            self.process = None
        if self.log:
            self.log.flush()
            self.log.seek(0)
            diagnostic = self.log.read()
            self.log.close()
            self.log = None
            if 'V08_AUDIT_FAILURE ' in diagnostic:
                failures = re.findall(r'V08_AUDIT_FAILURE stage=([a-z_]{1,40}) errno=([0-9]{1,4})', diagnostic)
                if failures:
                    for stage, code in sorted(set(failures))[:8]:
                        errors.append('Durable native audit write failed stage=' + stage +
                                      ' errno=' + code + '; records retained')
                else:
                    errors.append('Durable native audit write failed; records retained')
            if 'AddressSanitizer:' in diagnostic or 'runtime error:' in diagnostic:
                errors.append(diagnostic)
        self.directory.cleanup()
        if errors:
            raise RuntimeError('\n'.join(errors))
