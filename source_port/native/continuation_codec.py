"""Private exact-build checkpoint graph codec. SPDX-License-Identifier: GPL-3.0-or-later.

Only application-owned checkpoints are accepted; this is not an import format.
_source_identity is supplied by the native module from its hashed build inputs.
"""
import dis
import hashlib
import io
import platform
import socket
import sys
import cloudpickle

def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(source):
    return {'format':'SPELL-continuation/2', 'python':sys.version,
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


def encode(source, state, runtime=None):
    reject_resources((state,runtime))
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
    pickler.dump((state, exception_links((state,runtime)), runtime))
    payload = stream.getvalue()
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError('Experiment checkpoint exceeds 8 MiB')
    metadata = identity(source) | {'payload_sha256':sha(payload)}
    return metadata, payload


def decode(source, metadata, payload, with_runtime=False):
    expected = identity(source)
    if not isinstance(metadata, dict) or set(metadata) != set(expected) | {'payload_sha256'}:
        raise ValueError('Invalid checkpoint identity')
    if any(metadata[key] != expected[key] for key in expected):
        raise ValueError('Checkpoint source/runtime identity mismatch')
    if not isinstance(payload, bytes) or len(payload) > 8 * 1024 * 1024 or sha(payload) != metadata['payload_sha256']:
        raise ValueError('Checkpoint payload integrity mismatch')
    # Only application-owned files are accepted. Identity/CRC/hash checks detect
    # accidents; they do not turn pickle into an untrusted-data interchange format.
    state, links, runtime = cloudpickle.loads(payload)
    for error, cause, context, suppress, notes in links:
        error.__cause__ = cause
        error.__context__ = context
        error.__suppress_context__ = suppress
        if notes is not None:
            error.__notes__ = notes
    if with_runtime:
        return state,runtime
    if runtime:
        raise ValueError('Runtime data requires the full warm-start controller')
    return state


_runtime_names=frozenset(('ARGS','IVARS','PROC','SCDB','GDB'))


def capture_runtime():
    module=sys.modules.get('spell.runtime')
    return {key:vars(module)[key] for key in _runtime_names if key in vars(module)} if module else {}


def validate_runtime(saved):
    if saved is None:
        return
    if type(saved) is not dict or not set(saved).issubset(_runtime_names):
        raise ValueError('Invalid SPELL runtime data')
    if saved and 'spell.runtime' not in sys.modules:
        raise RuntimeError('SPELL runtime must be initialized before recovery')
    if 'PROC' in saved and type(saved['PROC']) is not dict:
        raise TypeError('Invalid procedure metadata')
    if 'ARGS' in saved or 'IVARS' in saved:
        from libSPELL_DTA_v3 import DataContainer
        if any(not isinstance(saved[key],DataContainer) for key in ('ARGS','IVARS') if key in saved):
            raise TypeError('Invalid native procedure data')


def restore_runtime(saved):
    validate_runtime(saved)
    if saved:
        # Objects were decoded in the same memo as all caller namespaces, so
        # imported aliases, closures and the active runtime share one graph.
        vars(sys.modules['spell.runtime']).update(saved)


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


def resume_saved(snapshot, probe, skip):
    if not isinstance(snapshot, list):
        return probe.resume_traced(snapshot)
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
                    skip(index, error)
                    continue
                resumed = probe.resume_error(capsule, error, entry.depth, entry.target, entry.lasti, True)
            else:
                resumed = probe.resume_traced(capsule)
            result, namespace, offset, slots = resumed
            error = None
        except BaseException as failure:
            error = failure
    if error is not None:
        raise error
    return result, namespace, offset, slots




def validate_chain(state, probe):
    if not isinstance(state, list) or not state or len(state)>128:
        raise ValueError('Invalid checkpoint chain extent')
    for index, row in enumerate(state):
        if type(row) is not tuple or len(row)!=2:
            raise ValueError('Invalid checkpoint frame entry')
        frame, delta = row
        if type(delta) is not int or (delta != 0 if index == 0 else delta <= 0):
            raise ValueError('Invalid caller return offset')
        candidate = list(frame)
        if index:
            candidate[4] += (None,)
            candidate[5] += b'\x00'
            candidate[6] += delta
        probe.from_state(tuple(candidate))
    return state
