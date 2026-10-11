"""Application-owned, exact-build checkpoint experiment; not an import format.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import dis
import importlib.util
import io
import os
from pathlib import Path
import platform
import socket
import sys
import tempfile
import cloudpickle


def load_native(name):
    path = next(Path('/out').glob(name + '*.so'))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


storage = load_native('_spell_storage_qualification')
probe = load_native('_recovery_probe')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(source):
    return {'format':'SPELL-persistent-probe/1', 'python':sys.version,
        'platform':platform.platform(), 'cloudpickle':cloudpickle.__version__,
        'source_sha256':sha(source), 'codec_sha256':sha(Path(__file__).read_bytes()),
        'backend_sha256':sha(Path(probe.__file__).read_bytes())}


def reject_resources(value, seen=None):
    if seen is None:
        seen = set()
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, (io.IOBase, socket.socket)):
        raise TypeError('Live external resources cannot be checkpointed')
    if isinstance(value, dict):
        for key, item in value.items():
            reject_resources(key, seen)
            reject_resources(item, seen)
    elif isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            reject_resources(item, seen)


def save(path, source, state, *, fail_before_replace=False):
    reject_resources(state)
    if cloudpickle.__version__ != '3.1.2':
        raise RuntimeError('Checkpoint codec requires qualified cloudpickle 3.1.2')
    stream = io.BytesIO()
    pickler = cloudpickle.CloudPickler(stream, protocol=5)
    # cloudpickle normally reconstructs a separate globals dictionary for
    # dynamic functions. Seed its version-pinned memo with the actual frame
    # namespace so subsequent global assignments affect those same functions.
    namespaces = [entry[0][1] for entry in state] if isinstance(state, list) else [state[1]]
    for namespace in namespaces:
        pickler.globals_ref[id(namespace)] = namespace
    pickler.dump((state, exception_links(state)))
    payload = stream.getvalue()
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError('Experiment checkpoint exceeds 8 MiB')
    metadata = identity(source) | {'payload_sha256':sha(payload)}
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    os.close(fd)
    try:
        writer = storage.create(temporary, 1)
        storage.store(writer, metadata)
        storage.store(writer, payload)
        del writer  # Close the real SPELL WS stream before fsync/replace.
        with open(temporary, 'rb') as stream:
            os.fsync(stream.fileno())
        if fail_before_replace:
            raise OSError('injected failure before commit')
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        for artifact in (temporary, temporary+'_READ', temporary+'_WRITE'):
            if os.path.exists(artifact):
                os.unlink(artifact)


def load(path, source):
    reader = storage.create(str(path), 0)
    metadata = storage.load(reader)
    expected = identity(source)
    if not isinstance(metadata, dict) or set(metadata) != set(expected) | {'payload_sha256'}:
        raise ValueError('Invalid checkpoint identity')
    if any(metadata[key] != expected[key] for key in expected):
        raise ValueError('Checkpoint source/runtime identity mismatch')
    payload = storage.load(reader)
    if not isinstance(payload, bytes) or len(payload) > 8 * 1024 * 1024 or sha(payload) != metadata['payload_sha256']:
        raise ValueError('Checkpoint payload integrity mismatch')
    # Only application-owned files are accepted. Identity/CRC/hash checks detect
    # accidents; they do not turn pickle into an untrusted-data interchange format.
    state, links = cloudpickle.loads(payload)
    for error, cause, context, suppress, notes in links:
        error.__cause__ = cause
        error.__context__ = context
        error.__suppress_context__ = suppress
        if notes is not None:
            error.__notes__ = notes
    if isinstance(state, list):
        if not state or len(state)>128:
            raise ValueError('Invalid checkpoint chain extent')
        for index, (frame, delta) in enumerate(state):
            if not isinstance(delta, int) or (delta != 0 if index == 0 else delta <= 0):
                raise ValueError('Invalid caller return offset')
            candidate = list(frame)
            if index:
                candidate[4] += (None,)
                candidate[5] += b'\x00'
                candidate[6] += delta
            probe.from_state(tuple(candidate))  # Validate every frame before executing any.
        return state
    return probe.from_state(state)


def resume_saved(snapshot):
    if not isinstance(snapshot, list):
        return probe.resume(snapshot)
    result = None
    error = None
    for index, (saved, delta) in enumerate(snapshot):
        frame = list(saved)
        if index and error is None:
            frame[4] += (result,)
            frame[5] += b'\x00'
            frame[6] += delta
        try:
            capsule = probe.from_state(tuple(frame))
            if error is not None:
                entry = next((entry for entry in dis.Bytecode(frame[0]).exception_entries
                    if entry.start <= frame[6]*2 < entry.end), None)
                if entry is None:
                    continue
                resumed = probe.resume_error(capsule, error, entry.depth, entry.target, entry.lasti)
            else:
                resumed = probe.resume(capsule)
            result, namespace, offset, slots = resumed
            error = None
        except BaseException as failure:
            error = failure
    if error is not None:
        raise error
    return result, namespace, offset, slots


def exception_links(root):
    # pickle deliberately omits traceback/context slots. Preserve the handled
    # exception graph explicitly, without retaining obsolete execution frames.
    pending, seen, links = [root], set(), []
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, BaseException):
            links.append((value, value.__cause__, value.__context__,
                value.__suppress_context__, getattr(value, '__notes__', None)))
            pending.extend((value.__cause__, value.__context__, value.args, vars(value)))
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            pending.extend(value)
    return links
