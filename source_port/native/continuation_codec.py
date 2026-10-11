"""Private exact-build checkpoint graph codec. SPDX-License-Identifier: GPL-3.0-or-later.

Only application-owned checkpoints are accepted; this is not an import format.
_source_identity is supplied by the native module from its hashed build inputs.
"""
import hashlib
import io
import platform
import socket
import sys
import cloudpickle

def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(source):
    return {'format':'SPELL-continuation/1', 'python':sys.version,
        'platform':platform.platform(), 'cloudpickle':cloudpickle.__version__,
        'source_sha256':sha(source), 'codec_sha256':_source_identity,
        'backend_sha256':_source_identity}


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


def encode(source, state):
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
    return metadata, payload


def decode(source, metadata, payload):
    expected = identity(source)
    if not isinstance(metadata, dict) or set(metadata) != set(expected) | {'payload_sha256'}:
        raise ValueError('Invalid checkpoint identity')
    if any(metadata[key] != expected[key] for key in expected):
        raise ValueError('Checkpoint source/runtime identity mismatch')
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
    return state


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
