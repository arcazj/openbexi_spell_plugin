"""Small bounded DAP framing shared by the host relay and headless client."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json

LIMIT = 4 * 1024 * 1024


def read(stream):
    length = None
    size = 0
    while True:
        line = stream.readline(8193)
        if not line:
            if size:
                raise ValueError('Incomplete DAP header')
            return None
        size += len(line)
        if size > 8192:
            raise ValueError('DAP header exceeds 8 KiB')
        if line == b'\r\n':
            break
        key, value = line.decode('ascii').split(':', 1)
        if key.lower() == 'content-length':
            if length is not None:
                raise ValueError('Duplicate DAP Content-Length')
            length = int(value)
    if length is None or not 0 < length <= LIMIT:
        raise ValueError('Invalid DAP message length')
    parts = bytearray()
    while len(parts) < length:
        part = stream.read(length - len(parts))
        if not part:
            raise ValueError('Incomplete DAP message')
        parts.extend(part)
    return json.loads(parts)


def write(stream, message):
    body = json.dumps(message, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(body) > LIMIT:
        raise ValueError('DAP message exceeds 4 MiB')
    stream.write(f'Content-Length: {len(body)}\r\n\r\n'.encode('ascii') + body)
    stream.flush()
