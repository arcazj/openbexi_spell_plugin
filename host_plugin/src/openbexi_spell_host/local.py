"""Packaged Linux learning desktop backend, with private project snapshots.

This runs inside the desktop's container, under its user account. It is a
Development teaching environment, not a sandbox for untrusted procedures.
"""
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile

from .container import Container


class LocalDesktop(Container):
    def __init__(self, project):
        super().__init__(project, 'packaged-native-desktop')
        manifest = Path('/opt/spell-native/runtime-manifest.json')
        if manifest.is_file():
            self.image = 'packaged-native-desktop:sha256:' + hashlib.sha256(manifest.read_bytes()).hexdigest()
        self.directory = None
        self.lock = None

    def start(self, *, stdin=subprocess.PIPE, stderr=None):
        import fcntl
        try:
            self.lock = open('/tmp/openbexi-native-desktop.lock', 'a+b')
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError('A native SPELL procedure is already open. Stop it before starting another.') from error
            self.directory = tempfile.TemporaryDirectory(prefix='openbexi-native-')
            workspace = Path(self.directory.name) / 'workspace'
            workspace.mkdir()
            with self.snapshot() as data, tarfile.open(fileobj=data) as archive:
                archive.extractall(workspace, filter='data')
            environment = dict(os.environ,
                OPENBEXI_SPELL_WORKSPACE=str(workspace),
                OPENBEXI_SPELL_DEMO_DSS='1',
                PATH='/opt/spell-native/bin:' + os.environ.get('PATH', ''))
            self.process = subprocess.Popen(
                ['/opt/spell-native/bin/python', '-I', '/opt/host/adapter.py'],
                cwd=workspace, env=environment, stdin=stdin, stdout=subprocess.PIPE,
                stderr=stderr, start_new_session=True)
            return self.process
        except BaseException:
            self.close()
            raise

    def export(self):
        if self.exported:
            return None
        # Reuse snapshot's file/link/size checks before preserving changed files.
        snapshot = Container(Path(self.directory.name) / 'workspace')
        with snapshot.snapshot() as source, tempfile.TemporaryFile() as output:
            with tarfile.open(fileobj=source) as incoming, tarfile.open(fileobj=output, mode='w') as outgoing:
                for item in incoming:
                    item.name = 'workspace/' + item.name
                    outgoing.addfile(item, incoming.extractfile(item) if item.isfile() else None)
            output.seek(0)
            return self.save_results(output)

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.send_signal(signal.SIGTERM)
            self.process.wait(timeout=45)
        if self.directory:
            self.directory.cleanup()
            self.directory = None
        if self.lock:
            self.lock.close()
            self.lock = None


def runtime(project, image=None):
    if os.environ.get('OPENBEXI_SPELL_BACKEND') == 'packaged-desktop':
        if os.name != 'posix' or image is not None:
            raise ValueError('The packaged desktop backend requires Linux and its installed runtime')
        return LocalDesktop(project)
    return Container(project, image)
