"""Owned local Development session using the installed original SPELL runtime."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET


class BridgeConnectionError(RuntimeError):
    """The initial IPC connection failed before any request was sent."""


class Bridge:
    def __init__(self, port, environment, log, events, *, connect_timeout=10):
        self.process = subprocess.Popen(['/bridge/spell-host-ipc', str(port)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            text=True, encoding='utf-8', env=environment)
        self.replies = queue.Queue()
        self.events = queue.Queue(maxsize=256)
        self.closing = threading.Event()
        self.sequence = 0
        self.thread = threading.Thread(target=self.read, name='native-ipc-reader')
        self.thread.start()
        try:
            first = self.replies.get(timeout=connect_timeout)
        except queue.Empty:
            self.close()
            raise BridgeConnectionError('Native bridge connection timed out')
        if first.get('event') != 'connected':
            self.close()
            raise BridgeConnectionError('Native IPC could not connect: ' + str(first))
        self.events = events

    def read(self):
        try:
            for line in self.process.stdout:
                item = json.loads(line)
                if 'seq' in item or item.get('event') == 'connected':
                    self.replies.put(item)
                else:
                    self.publish(item)
        except Exception as error:
            self.publish({'event': 'connectionError', 'error': str(error)})
        finally:
            self.replies.put({'error': 'Native bridge ended'})

    def publish(self, item):
        while not self.closing.is_set():
            try:
                self.events.put(item, timeout=.1)
                return
            except queue.Full:
                continue

    def exchange(self, identifier, receiver, fields=None, *, send=False, pump=None):
        self.sequence += 1
        self.process.stdin.write(json.dumps({'seq': self.sequence,
            'operation': 'send' if send else 'request', 'id': identifier,
            'receiver': receiver, 'fields': fields or {}}) + '\n')
        self.process.stdin.flush()
        deadline = time.monotonic() + 10
        while True:
            # Notifications and replies share one wire. Keep forwarding the
            # bounded event queue while awaiting a reply behind a burst.
            if pump:
                pump()
            try:
                reply = self.replies.get(timeout=.05)
                break
            except queue.Empty as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'{identifier}: Native reply timed out') from error
        if reply.get('seq') != self.sequence or not reply.get('ok'):
            raise RuntimeError(f'{identifier}: {reply}')
        return reply.get('message', {}).get('fields', {})

    def close(self):
        self.closing.set()
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except BrokenPipeError:
                pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.thread.join(timeout=5)
        self.process.stdout.close()


class NativeSession:
    def __init__(self, project, script, arguments, *, driver_port=None, user_library=None):
        self.driver_port = driver_port
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
                              connect_timeout=min(10, remaining))
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
        if self.user_library is not None:
            environment['OPENBEXI_SPELL_USER_LIBRARY'] = str(self.user_library)
            environment['OPENBEXI_SPELL_ENTRYPOINT'] = str(self.script)
        if self.driver_port:
            environment['OPENBEXI_DRIVER_RELAY_PORT'] = str(self.driver_port)
        self.log = (root / 'native.log').open('w+')
        self.process = subprocess.Popen(['spell-native', 'listener', '-c', example['config']],
            cwd=self.project, env=environment, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True)
        deadline = time.monotonic() + 10
        self.listener = self.connect_bridge(9980, environment, deadline)
        self.listener.exchange('REQ_GUI_LOGIN', 'LST',
            {'ContextName': 'example', 'Host': 'openbexi-host-v1', 'GuiMode': 'Development'})
        while time.monotonic() < deadline:
            info = self.listener.exchange('REQ_CTX_INFO', 'LST', {'ContextName': 'example'})
            if info.get('ContextStatus') == 'RUNNING':
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Native context startup timed out')
        # RUNNING is listener bookkeeping; the context IPC accept thread can
        # still be starting. Retry only connection setup, never a sent request.
        self.context = self.connect_bridge(int(info['ContextPort']), environment, deadline)
        self.context.exchange('REQ_GUI_LOGIN', 'CTX', {'Host': 'openbexi-host-v1'})
        self.request('REQ_OPEN_EXEC', context=True, fields={'GuiMode': 'CONTROL',
            'Arguments': self.arguments, 'OpenMode': '{Automatic:True,Visible:True,Blocking:False}'})
        self.opened = True
        deadline = time.monotonic() + 15
        paused_notification = False
        while time.monotonic() < deadline:
            # Drain startup notifications before handing control to a host.
            # Context status can change before its GUI notification arrives.
            while not self.events.empty():
                item = self.events.get_nowait()
                fields = item.get('message', {}).get('fields', {})
                if fields.get('DataType') == 'STATUS' and fields.get('ExecutorStatus') == 'PAUSED':
                    paused_notification = True
                if item.get('event') == 'connectionError':
                    raise RuntimeError(item.get('error', 'Native connection failed'))
            info = self.request('REQ_EXEC_INFO', context=True)
            if info.get('ExecutorStatus') == 'PAUSED' and paused_notification:
                return
            if info.get('ExecutorStatus') in {'ERROR', 'ABORTED'}:
                raise RuntimeError('Native procedure could not open: ' + str(info))
            time.sleep(.05)
        raise RuntimeError('Native procedure startup timed out: ' + str(info) +
                           '; paused notification: ' + str(paused_notification))

    def request(self, identifier, fields=None, *, context=False, send=False, procedure=None):
        target = self.instance if procedure is None else procedure
        return self.context.exchange(identifier, 'CTX' if context else target,
            dict(fields or {}, ProcId=target), send=send, pump=self.pump)

    def close(self):
        errors = []
        if self.context:
            try:
                if self.opened:
                    self.request('REQ_CLOSE_EXEC', context=True)
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
            if 'AddressSanitizer:' in diagnostic or 'runtime error:' in diagnostic:
                errors.append(diagnostic)
        self.directory.cleanup()
        if errors:
            raise RuntimeError('\n'.join(errors))
