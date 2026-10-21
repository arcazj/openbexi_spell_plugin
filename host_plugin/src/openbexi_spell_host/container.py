"""Private project snapshots and owned native containers; no host bind mounts."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import threading
import uuid

MAX_FILE = 32 * 1024 * 1024
MAX_PROJECT = 256 * 1024 * 1024
EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
            '.session', '.qualification', '.openbexi', '.idea', 'build', 'dist'}


def included(parts):
    return not any(part in EXCLUDED or part == '.env' or part.startswith('.env.') for part in parts)


def valid_result_part(part):
    # Artifacts must have portable names, including when a Linux procedure
    # produces files which Windows would interpret as devices or data streams.
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                *(f'LPT{i}' for i in range(1, 10))}
    return (bool(part) and part not in {'.', '..'} and not part.endswith(('.', ' '))
            and not any(ord(ch) < 32 or ch in '<>:"/\\|?*' for ch in part)
            and part.split('.', 1)[0].upper() not in reserved)


def command(arguments, **options):
    return subprocess.run(['docker', *arguments], capture_output=True, check=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, **options)


class Container:
    def __init__(self, project, image=None):
        self.project = Path(project).resolve(strict=True)
        if not self.project.is_dir():
            raise ValueError('Project must be a folder')
        self.id = uuid.uuid4().hex
        self.name = 'openbexi-spell-' + self.id
        self.image = image or os.environ.get('OPENBEXI_SPELL_IMAGE', 'openbexi-spell-dss:0.7.0')
        self.inputs = {}
        self.created = False
        self.process = None
        self.exported = False

    def snapshot(self):
        temporary = tempfile.TemporaryFile()
        total = 0
        try:
            with tarfile.open(fileobj=temporary, mode='w') as archive:
                for directory, subdirs, files in os.walk(self.project, followlinks=False):
                    subdirs[:] = sorted(name for name in subdirs if included((name,)))
                    base = Path(directory)
                    if not base.resolve().is_relative_to(self.project):
                        raise ValueError('Project directory escapes the selected folder')
                    if base != self.project:
                        info = tarfile.TarInfo(base.relative_to(self.project).as_posix())
                        info.type = tarfile.DIRTYPE
                        info.mode = 0o755
                        info.uid = info.gid = 10003
                        archive.addfile(info)
                    for name in subdirs:
                        if (base / name).is_symlink() or (base / name).is_junction():
                            raise ValueError('Project snapshots do not follow directory symlinks: ' + name)
                    for name in sorted(files):
                        path = base / name
                        relative = path.relative_to(self.project)
                        if not included(relative.parts):
                            continue
                        if path.is_symlink() or not path.is_file():
                            raise ValueError('Project snapshots require regular files: ' + str(relative))
                        with path.open('rb') as source:
                            content = source.read(MAX_FILE + 1)
                        total += len(content)
                        if len(content) > MAX_FILE or total > MAX_PROJECT:
                            raise ValueError('Project snapshot exceeds 32 MiB per file or 256 MiB total')
                        name = relative.as_posix()
                        self.inputs[name] = hashlib.sha256(content).hexdigest()
                        info = tarfile.TarInfo(name)
                        info.size = len(content)
                        info.mode = 0o644
                        info.uid = info.gid = 10003
                        archive.addfile(info, io.BytesIO(content))
            temporary.seek(0)
            return temporary
        except BaseException:
            temporary.close()
            raise

    def start(self, *, stdin=subprocess.PIPE, stderr=None):
        try:
            self.image = command(['image', 'inspect', self.image, '--format', '{{.Id}}'], text=True).stdout.strip()
            with self.snapshot() as archive:
                command(['create', '--rm', '--init', '-i', '-a', 'stdin', '-a', 'stdout', '-a', 'stderr',
                    '--name', self.name, '--label', 'org.openbexi.spell.host=1',
                    '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                    '--pids-limit', '256', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m', self.image])
                self.created = True
                command(['cp', '-a', '-', self.name + ':/workspace'], stdin=archive)
            self.process = subprocess.Popen(['docker', 'start', '-ai', self.name], stdin=stdin,
                stdout=subprocess.PIPE, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return self.process
        except BaseException:
            self.close()
            raise

    def export(self):
        if self.exported:
            return None
        # The native adapter sends terminated after closing the executor. It
        # remains connected until disconnect, so outputs can be copied now.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(['docker', 'cp', self.name + ':/workspace', '-'],
                stdout=subprocess.PIPE, stderr=errors,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            expired = threading.Event()
            def expire():
                expired.set()
                process.kill()
            timer = threading.Timer(30, expire)
            timer.start()
            try:
                total = 0
                while chunk := process.stdout.read(65536):
                    total += len(chunk)
                    if total > MAX_PROJECT + 16 * 1024 * 1024:
                        raise ValueError('Result archive exceeds the project snapshot limit')
                    output.write(chunk)
                code = process.wait(timeout=5)
                if expired.is_set():
                    raise TimeoutError('Result export exceeded 30 seconds')
                if code:
                    errors.seek(0)
                    raise RuntimeError(errors.read(65536).decode('utf-8', 'replace'))
            finally:
                timer.cancel()
                timer.join()
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                process.stdout.close()
            output.seek(0)
            return self.save_results(output)

    def save_results(self, output):
        destination = self.project / '.openbexi' / 'runs' / self.id
        if any(path.is_symlink() or path.is_junction()
               for path in (self.project / '.openbexi', self.project / '.openbexi/runs')):
            raise ValueError('Output directory cannot be a symlink')
        destination.mkdir(parents=True, exist_ok=False)
        changed, present = {}, set()
        total = 0
        host_names = set()
        with tarfile.open(fileobj=output, mode='r:') as archive:
            for member in archive:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] != 'workspace' or '..' in parts or '\\' in member.name:
                    raise ValueError('Invalid result archive path')
                relative = PurePosixPath(*parts[1:])
                if not included(relative.parts) or member.isdir():
                    continue
                if not relative.parts or not all(valid_result_part(part) for part in relative.parts):
                    raise ValueError('Result contains a non-portable filename')
                if not member.isfile() or member.size > MAX_FILE:
                    raise ValueError('Result contains a link or oversized file')
                total += member.size
                if total > MAX_PROJECT:
                    raise ValueError('Results exceed 256 MiB')
                name = relative.as_posix()
                host_name = os.path.normcase(name)
                if name in present or host_name in host_names:
                    raise ValueError('Duplicate or conflicting result path')
                present.add(name)
                host_names.add(host_name)
                content = archive.extractfile(member).read()
                digest = hashlib.sha256(content).hexdigest()
                if self.inputs.get(name) == digest:
                    continue
                target = destination / 'artifacts' / Path(*relative.parts)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise ValueError('Result path escapes the run directory')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                changed[name] = digest
        report = {'run': self.id, 'image': self.image, 'inputs': self.inputs,
                  'artifacts': changed, 'deleted_in_snapshot': sorted(self.inputs.keys() - present)}
        (destination / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        self.exported = True
        return destination

    def close(self):
        if self.created:
            result = subprocess.run(['docker', 'rm', '-f', self.name], capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode and b'No such container' not in result.stderr:
                raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
            self.created = False
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
