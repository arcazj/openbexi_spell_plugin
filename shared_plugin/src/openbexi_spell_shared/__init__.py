"""Original native SPELL provider for durable Development and approved Execution."""
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import deque
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import tarfile
import tempfile
import threading
import time
from urllib.parse import urlsplit

from openbexi_spell_host.protocol import read, write

# Durable binding protocol version; retained across distribution upgrades.
VERSION = '0.4.0'
PROFILE = 'spell-native-shared-development/1'
DSS_PROFILE = 'spell-native-shared-dss/1'
EXECUTION_PROFILE = 'spell-native-dss-execution/1'


def docker(*args, **options):
    result = subprocess.run(['docker', *args], capture_output=True, timeout=options.pop('timeout', 20),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, **options)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace')[:8192])
    return result.stdout


def identities(session, procedure):
    if any(re.fullmatch('[0-9a-f]{32}', item) is None for item in (session, procedure)):
        raise ValueError('Invalid shared worker identity')
    return 'openbexi-native-shared-' + session + '-' + procedure, {
        'org.openbexi.shared.session': session, 'org.openbexi.shared.procedure': procedure}


def validate(binding):
    dss = type(binding) is dict and binding.get('profile') in {DSS_PROFILE,EXECUTION_PROFILE}
    execution = type(binding) is dict and binding.get('profile') == EXECUTION_PROFILE
    keys = {'profile','version','image'} | ({'driver'} if dss else set()) | ({'release'} if execution else set())
    if (type(binding) is not dict or set(binding) != keys
            or binding['profile'] not in {PROFILE,DSS_PROFILE,EXECUTION_PROFILE}
            or binding['version'] not in ({VERSION,'0.4.0.dev1'} if binding['profile'] == PROFILE else {VERSION})
            or re.fullmatch('sha256:[0-9a-f]{64}', binding['image']) is None):
        raise ValueError('Unsupported native shared runtime binding')
    if dss:
        driver = binding['driver']
        if (type(driver) is not dict or set(driver) not in ({'url','host','port'}, {'url','host','port','kafka'})
                or type(driver['url']) is not str or len(driver['url']) > 2048
                or type(driver['host']) is not str or not 1 <= len(driver['host']) <= 253
                or type(driver['port']) is not int or not 1 <= driver['port'] <= 65535):
            raise ValueError('Invalid service-owned DSS binding')
        endpoint = urlsplit(driver['url'])
        if (endpoint.scheme not in {'http','https'} or not endpoint.hostname or endpoint.username
                or endpoint.password or endpoint.query or endpoint.fragment):
            raise ValueError('DSS binding requires an endpoint without embedded credentials')
        if 'kafka' in driver and (type(driver['kafka']) is not str
                or re.fullmatch(r'[A-Za-z0-9.-]{1,253}:[0-9]{1,5}',driver['kafka']) is None
                or not 1 <= int(driver['kafka'].rsplit(':',1)[1]) <= 65535):
            raise ValueError('Kafka requires one explicit host:port endpoint')
    if execution and (type(binding['release']) is not str or re.fullmatch('[0-9a-f]{64}',binding['release']) is None):
        raise ValueError('Invalid approved native release identity')


def owned(name, labels, image):
    rows = docker('ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}').decode().splitlines()
    if not rows:
        return None
    info = json.loads(docker('inspect', name))[0]
    actual = info['Config'].get('Labels') or {}
    if any(actual.get(key) != value for key, value in labels.items()) or info['Image'] != image:
        raise ValueError('Native shared container ownership differs; maintenance required')
    return info


class Provider:
    api = 1

    @staticmethod
    def for_release(manifest):
        if manifest.get('profile') != 'plugin-docker-isolated/1' or manifest.get('backend',{}).get('provider') != 'spell':
            raise ValueError('Unsupported original native Execution release')
        binding = manifest['backend']['binding']
        validate(binding)
        if binding['profile'] != DSS_PROFILE or binding['image'] != manifest['base_image']:
            raise ValueError('Native Execution requires an explicitly bound DSS runtime')
        raw = json.dumps(manifest,sort_keys=True,separators=(',', ':'),ensure_ascii=True,allow_nan=False)
        result = dict(binding,profile=EXECUTION_PROFILE,image=manifest['image'],release=hashlib.sha256(raw.encode()).hexdigest())
        validate(result)
        return result

    @staticmethod
    def bind():
        image = os.environ.get('OPENBEXI_SPELL_SHARED_IMAGE', 'openbexi-spell-dss:0.7.0')
        info = json.loads(docker('image', 'inspect', image))[0]
        if info['Os'] != 'linux' or info['Architecture'] != 'amd64':
            raise ValueError('Native shared runtime requires the Linux amd64 host image')
        binding = {'profile': PROFILE, 'version': VERSION, 'image': info['Id']}
        if os.environ.get('OPENBEXI_SPELL_DSS_URL'):
            address = os.environ['OPENBEXI_SPELL_DSS_TCP'].rsplit(':',1)
            binding.update(profile=DSS_PROFILE,driver=dict(url=os.environ['OPENBEXI_SPELL_DSS_URL'],host=address[0],port=int(address[1])))
            if os.environ.get('OPENBEXI_SPELL_DSS_KAFKA'):
                binding['driver']['kafka'] = os.environ['OPENBEXI_SPELL_DSS_KAFKA']
        validate(binding)
        return binding

    @staticmethod
    def create(session, procedure, binding, project, script, arguments, *, results):
        return Worker(session, procedure, binding, project, script, arguments, results=results)

    @staticmethod
    def recover(session, procedure, binding):
        validate(binding)
        name, labels = identities(session, procedure)
        info = owned(name, labels, binding['image'])
        if info:
            docker('rm', '--force', info['Id'])


provider = Provider()


class Worker:
    def __init__(self, session, procedure, binding, project, script, arguments, *, results):
        validate(binding)
        if len(arguments) > 1:
            raise ValueError('Native shared arguments require one JSON object')
        if arguments and type(json.loads(arguments[0])) is not dict:
            raise ValueError('Native shared arguments require one JSON object')
        self.name, self.labels = identities(session, procedure)
        self.binding, self.project, self.script = binding, Path(project), script
        self.arguments = arguments
        self.results, self.procedure = Path(results), procedure
        self.process, self.identifier = None, None
        self.lock = threading.RLock()
        self.closed, self.running, self.frozen = False, False, False
        self.sequence, self.exit_code = 0, None
        self.incoming, self.pending = queue.Queue(maxsize=256), deque()
        self.threads, self.read_error = [], None
        self.inputs = {}
        self.output_chunks = deque()
        self.bootstrap_pids = None
        self.driver = self.driver_journal = self.driver_transport = None
        self.execution = binding['profile'] == EXECUTION_PROFILE
        self.request_handler = None
        self.write_lock = threading.Lock()
        self.heartbeat_done = threading.Event()

    def set_request_handler(self,handler):
        self.request_handler = handler

    def inspect(self):
        info = owned(self.name, self.labels, self.binding['image'])
        if not info or info['Id'] != self.identifier:
            raise ValueError('Native shared owned container disappeared')
        return info

    def process_ids(self):
        lines = docker('top', self.identifier, '-eo', 'pid,stat').decode().splitlines()[1:]
        return {int(line.split()[0]) for line in lines if not line.split()[1].startswith('Z')}

    def snapshot(self):
        result = tempfile.TemporaryFile()
        try:
            total, count = 0, 0
            with tarfile.open(fileobj=result, mode='w') as archive:
                for path in sorted(self.project.rglob('*')):
                    if path.is_symlink() or path.is_junction():
                        raise ValueError('Native snapshots cannot contain links')
                    if path.is_dir():
                        info = tarfile.TarInfo(path.relative_to(self.project).as_posix())
                        info.type, info.mode, info.uid, info.gid = tarfile.DIRTYPE, 0o755, 10003, 10003
                        archive.addfile(info)
                        continue
                    if not path.is_file():
                        raise ValueError('Native snapshots require regular files')
                    data = path.read_bytes()
                    total, count = total + len(data), count + 1
                    if len(data) > 8 * 1024 * 1024 or total > 64 * 1024 * 1024 or count > 4096:
                        raise ValueError('Native snapshot exceeds capture bounds')
                    name = path.relative_to(self.project).as_posix()
                    self.inputs[name] = hashlib.sha256(data).hexdigest()
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.uid, info.gid = len(data), 0o644, 10003, 10003
                    archive.addfile(info, io.BytesIO(data))
            result.seek(0)
            return result
        except BaseException:
            result.close()
            raise

    def _read(self, stream, protocol):
        try:
            if protocol:
                while message := read(stream):
                    self.incoming.put_nowait(message)
                self.incoming.put_nowait({'type': 'eof'})
            else:
                while raw := stream.read1(4096):
                    self.incoming.put_nowait({'type': 'event', 'event': 'output',
                        'body': {'category': 'stderr', 'output': raw.decode('utf-8', 'replace')}})
        except BaseException as error:
            self.read_error = str(error) or type(error).__name__

    def next(self, timeout=.05):
        if self.read_error:
            raise RuntimeError('Native shared transport failed: ' + self.read_error)
        try:
            message = self.incoming.get(timeout=timeout)
        except queue.Empty:
            return None
        if message.get('type') == 'eof':
            raise EOFError('Native shared adapter ended before confirmed completion')
        return message

    def request(self, command, **arguments):
        self.sequence += 1
        sequence = self.sequence
        with self.write_lock:
            write(self.process.stdin, {'seq': sequence, 'type': 'request', 'command': command, 'arguments': arguments})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            message = next((m for m in self.pending if m.get('type') == 'response' and m.get('request_seq') == sequence),None)
            if message is not None:
                self.pending.remove(message)
            else:
                message = self.next()
            if message is None:
                continue
            if message.get('type') == 'response' and message.get('request_seq') == sequence:
                if not message.get('success'):
                    raise RuntimeError(message.get('message', 'Native request rejected'))
                return message.get('body', {})
            if (message.get('event') == 'openbexi/driverRequest' and self.request_handler
                    and command != 'openbexi/freezeWatchdog'):
                self.request_handler({'type':'backend_request','request':message['body']})
                continue
            if len(self.pending) >= 256:
                raise ValueError('Native shared pending event bound exceeded')
            self.pending.append(message)
        raise TimeoutError('Native shared request timed out: ' + command)

    def heartbeat(self):
        try:
            while not self.heartbeat_done.wait(.5):
                if not self.frozen:
                    with self.write_lock:
                        write(self.process.stdin,{'type':'event','event':'openbexi/heartbeat'})
        except (OSError,ValueError):
            return

    def start(self):
        with self.lock:
            if self.closed:
                raise ValueError('Native shared worker already closed')
            if owned(self.name, self.labels, self.binding['image']):
                raise ValueError('Native shared container already exists; recovery required')
            if self.binding['profile'] in {DSS_PROFILE,EXECUTION_PROFILE}:
                from openbexi_spell_dss.transport import Transport
                from openbexi_spell_dss.operational_journal import Journal
                from openbexi_spell_dss.rpc import Dispatcher
                settings = self.binding['driver']
                self.driver_transport = Transport.from_binding(settings)
                self.driver_journal = Journal(self.results.parent / 'driver-effects.sqlite')
                users = {}
                users_path = os.environ.get('OPENBEXI_SPELL_DSS_USERS')
                if users_path:
                    raw = Path(users_path).read_bytes()
                    if len(raw) > 65536:
                        raise ValueError('Simulator user file exceeds bounds')
                    users = json.loads(raw)
                    if (type(users) is not dict or len(users) > 128
                            or any(type(k) is not str or re.fullmatch('[A-Za-z0-9_.-]{1,96}',k) is None
                                   or type(v) is not str or re.fullmatch('[0-9a-f]{64}',v) is None for k,v in users.items())):
                        raise ValueError('Invalid service-owned simulator account file')
                self.driver = Dispatcher(self.driver_transport,self.driver_journal,users=users)
            labels = [arg for key, value in self.labels.items() for arg in ('--label', key + '=' + value)]
            security = ['--read-only','--user','10003:10003','--workdir','/tmp','--entrypoint','python'] if self.execution else []
            if self.execution:
                options = json.loads(docker('info','--format','{{json .SecurityOptions}}'))
                if not any('seccomp' in option for option in options):
                    raise ValueError('Native Execution requires Docker seccomp support')
            self.identifier = docker('create', '--init', '-i', '--name', self.name, *labels,
                    '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                    '--pids-limit', '256', '--memory', '1g', '--memory-swap', '1g', '--cpus', '1',
                    '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=256m', *security,self.binding['image'],
                    *(['-I','/opt/host/adapter.py'] if self.execution else [])).decode().strip()
            if self.execution:
                info = self.inspect()
                host = info['HostConfig']
                if (info['Mounts'] or not host['ReadonlyRootfs'] or host['Privileged']
                        or host['NetworkMode'] != 'none' or info['Config']['User'] != '10003:10003'):
                    raise ValueError('Native Execution isolation configuration differs')
            else:
                with self.snapshot() as archive:
                    docker('cp', '-a', '-', self.identifier + ':/workspace', stdin=archive)
            self.process = subprocess.Popen(['docker', 'start', '-ai', self.identifier],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for stream, protocol in ((self.process.stdout, True), (self.process.stderr, False)):
                thread = threading.Thread(target=self._read, args=(stream, protocol), daemon=True)
                self.threads.append(thread)
                thread.start()
            if self.driver:
                thread = threading.Thread(target=self.heartbeat,name='native-parent-heartbeat',daemon=True)
                self.threads.append(thread)
                thread.start()
            self.request('initialize', adapterID='spell', linesStartAt1=True, pathFormat='path',privateWatchdog=self.driver is not None)
            self.bootstrap_pids = self.process_ids()
            self.request('launch', project=str(self.project), program=str(self.project / self.script),
                         args=list(self.arguments), noDebug=False, stopOnEntry=True,driverRelay=self.driver is not None,
                         immutableRelease=self.execution)
            self.request('configurationDone')

    def resume(self):
        with self.lock:
            if self.closed:
                raise ValueError('Native shared worker closed')
            if self.frozen:
                self.inspect()
                docker('unpause', self.identifier)
                if self.inspect()['State']['Paused']:
                    raise ValueError('Native shared resume unconfirmed')
                self.frozen = False
            if not self.running:
                self.request('continue', threadId=1)
                self.running = True

    def pause(self):
        with self.lock:
            if self.closed:
                raise ValueError('Native shared worker closed')
            info = self.inspect()
            if not info['State']['Paused']:
                if self.driver:
                    self.request('openbexi/freezeWatchdog')
                docker('pause', self.identifier)
            state = self.inspect()['State']
            if not state['Running'] or not state['Paused']:
                raise ValueError('Native whole-container quiescence unconfirmed')
            self.frozen = True

    def input(self, text):
        with self.lock:
            if text is None:
                raise ValueError('Native prompt input EOF requires stop and reconciliation')
            self.request('openbexi/input', text=text)

    def poll(self):
        if self.output_chunks:
            return self.output_chunks.popleft()
        message = self.pending.popleft() if self.pending else self.next()
        if message is None or message.get('type') != 'event':
            return None
        body, event = message.get('body', {}), message.get('event')
        if event == 'openbexi/driverRequest':
            return {'type':'backend_request','request':body}
        if event == 'output':
            text = body.get('output', '')
            if not isinstance(text, str) or len(text) > 1024 * 1024:
                raise ValueError('Native shared output exceeds transport bound')
            stream = 'stderr' if body.get('category') == 'stderr' else 'stdout'
            # 4096 Unicode characters fit the neutral 64 KiB JSON event bound,
            # including non-BMP text encoded as JSON surrogate pairs.
            self.output_chunks.extend({'type': 'output', 'stream': stream, 'text': text[i:i+4096]}
                                      for i in range(0, len(text), 4096))
            return self.output_chunks.popleft() if self.output_chunks else None
        if event == 'openbexi/inputRequest':
            return {'type': 'output', 'stream': 'stdout', 'text': 'Native prompt choices: ' + str(body.get('choices', '')) +
                ' (answer with native option index)\n'}
        if event == 'exited':
            self.exit_code = body['exitCode']
        if event == 'terminated':
            if type(self.exit_code) is not int:
                raise ValueError('Native termination has no exit receipt')
            if self.bootstrap_pids is None or not self.process_ids().issubset(self.bootstrap_pids):
                raise ValueError('Native descendant shutdown unconfirmed')
            if not self.execution:
                from openbexi_spell_host.container import Container
                self.results.mkdir(parents=True, exist_ok=True)
                exporter = Container(self.results, image=self.binding['image'])
                exporter.name, exporter.id, exporter.inputs = self.identifier, self.procedure, self.inputs
                exporter.export()
            return {'type': 'finished', 'exit_code': self.exit_code}
        return None

    def handle_request(self,event,identity,check):
        if self.driver is None:
            raise ValueError('Unexpected native driver request')
        body = event['request']
        if type(body) is not dict or set(body) != {'id','path','payload'} or len(body['payload']) > 90000:
            raise ValueError('Invalid native driver request')
        raw = base64.b64decode(body['payload'],validate=True)
        result = self.driver.dispatch(body['path'],raw,identity,body['id'],check)
        self.request('openbexi/driverReply',id=body['id'],payload=base64.b64encode(result).decode('ascii'))

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.heartbeat_done.set()
            if self.identifier:
                info = owned(self.name, self.labels, self.binding['image'])
                if info:
                    if info['Id'] != self.identifier:
                        raise ValueError('Native shared container identity changed')
                    docker('rm', '--force', self.identifier)
            if self.process:
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=5)
                for thread in self.threads:
                    thread.join(timeout=5)
                    if thread.is_alive():
                        raise RuntimeError('Native shared transport shutdown unconfirmed')
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    try:
                        stream.close()
                    except OSError:
                        if not stream.closed:
                            stream.raw.close()
            if self.driver_transport:
                self.driver_transport.close()
                self.driver_transport = None
            if self.driver_journal:
                self.driver_journal.close()
                self.driver_journal = None
            self.closed = True
