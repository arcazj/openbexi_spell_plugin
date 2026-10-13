"""Bounded codec compatible with original spell.utils.grpc_utils Any values."""
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass
import math
from google.protobuf.any_pb2 import Any
from google.protobuf import wrappers_pb2 as w
from .stubs import SPELLDriver_pb2 as p

MAX_BYTES = 65536


@dataclass(frozen=True)
class Time:
    text: str


def _budget(depth, nodes):
    nodes[0] -= 1
    if depth > 12 or nodes[0] < 0:
        raise ValueError('Driver value nesting/node bound exceeded')


def pack(value, _depth=0, _nodes=None):
    nodes = [2048] if _nodes is None else _nodes
    _budget(_depth, nodes)
    def child(item):
        return pack(item, _depth + 1, nodes)
    if value is None:
        message = Any()  # Original PackValue(None) packs an empty Any inside Any.
    elif type(value) in {bool, int, float, str, bytes}:
        if isinstance(value, (str, bytes)) and len(value) > 8192:
            raise ValueError('Driver scalar bound exceeded')
        if type(value) is float and not math.isfinite(value):
            raise ValueError('Nonfinite driver scalar')
        message = {bool:w.BoolValue, int:w.Int64Value, float:w.DoubleValue,
                   str:w.StringValue, bytes:w.BytesValue}[type(value)](value=value)
    elif type(value) is Time:
        if len(value.text) > 128:
            raise ValueError('Driver time bound exceeded')
        message = p.Time(timeMsg=value.text)
    elif type(value) in {list, tuple}:
        if len(value) > 256:
            raise ValueError('Driver list bound exceeded')
        message = p.List(entries=[child(item) for item in value])
    elif type(value) is dict:
        if len(value) > 128:
            raise ValueError('Driver dictionary bound exceeded')
        message = p.Dict()
        for key, item in value.items():
            if type(key) not in {str, int, bool}:
                raise ValueError('Unsupported driver dictionary key')
            message.entries.add(key=child(key), value=child(item))
    else:
        raise ValueError('Unsupported driver value type')
    result = Any()
    result.Pack(message)
    if result.ByteSize() > MAX_BYTES:
        raise ValueError('Driver value byte bound exceeded')
    return result


_TYPES = {cls.DESCRIPTOR.full_name:cls for cls in
          (w.BoolValue, w.BytesValue, w.DoubleValue, w.FloatValue, w.Int32Value,
           w.Int64Value, w.UInt32Value, w.StringValue, p.Dict, p.List, p.Time, Any)}


def unpack(value, _depth=0, _nodes=None):
    nodes = [2048] if _nodes is None else _nodes
    _budget(_depth, nodes)
    if value.ByteSize() > MAX_BYTES:
        raise ValueError('Driver value byte bound exceeded')
    cls = _TYPES.get(value.TypeName())
    if cls is None:
        raise ValueError('Unknown driver Any type')
    message = cls()
    if not value.Unpack(message):
        raise ValueError('Invalid driver Any payload')
    def child(item):
        return unpack(item, _depth + 1, nodes)
    if cls is Any:
        if message.ByteSize():
            raise ValueError('Nested arbitrary Any is unsupported')
        return None
    if cls is p.Dict:
        if len(message.entries) > 128:
            raise ValueError('Driver dictionary bound exceeded')
        result = {}
        for entry in message.entries:
            key = child(entry.key)
            if type(key) not in {str, int, bool} or key in result:
                raise ValueError('Duplicate or unsupported driver dictionary key')
            result[key] = child(entry.value)
        return result
    if cls is p.List:
        if len(message.entries) > 256:
            raise ValueError('Driver list bound exceeded')
        return [child(item) for item in message.entries]
    if cls is p.Time:
        if len(message.timeMsg) > 128:
            raise ValueError('Driver time bound exceeded')
        return Time(message.timeMsg)
    result = message.value
    if isinstance(result, (str, bytes)) and len(result) > 8192:
        raise ValueError('Driver scalar bound exceeded')
    if type(result) is float and not math.isfinite(result):
        raise ValueError('Nonfinite driver scalar')
    return result
