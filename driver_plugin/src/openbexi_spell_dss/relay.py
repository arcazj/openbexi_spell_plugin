"""In-container original RPC -> bounded private parent pipe relay."""

# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import queue
import threading
import uuid
from .server import Server


class Relay:
    def __init__(self, emit, *, runtime_epochs=False):
        self.emit, self.lock, self.pending = emit, threading.Lock(), {}
        self.closed = False
        self.server = Server(self.call, runtime_epochs=runtime_epochs)
        self.port = self.server.port

    def call(self, path, raw, runtime_epoch=None):
        identity = uuid.uuid4().hex
        inbox = queue.Queue(maxsize=1)
        with self.lock:
            if self.closed or len(self.pending) >= 4:
                raise RuntimeError("Driver relay is closed or full")
            self.pending[identity] = inbox
        try:
            self.emit(
                "openbexi/driverRequest",
                id=identity,
                path=path,
                payload=base64.b64encode(raw).decode("ascii"),
                **(
                    {"runtime_epoch": runtime_epoch}
                    if runtime_epoch is not None
                    else {}
                ),
            )
            answer = inbox.get(timeout=35)
            if answer.get("error"):
                raise RuntimeError("Parent driver request rejected")
            raw = base64.b64decode(answer["payload"], validate=True)
            if len(raw) > 65536:
                raise ValueError("Driver reply exceeds bounds")
            return raw
        finally:
            with self.lock:
                self.pending.pop(identity, None)

    def reply(self, answer):
        if type(answer) is not dict or set(answer) not in (
            {"id", "payload"},
            {"id", "error"},
        ):
            raise ValueError("Invalid parent driver reply")
        with self.lock:
            inbox = self.pending.get(answer["id"])
            if inbox is None:
                raise ValueError("Unknown driver reply identity")
            inbox.put_nowait(answer)

    def close(self):
        with self.lock:
            self.closed = True
            for identity, inbox in self.pending.items():
                try:
                    inbox.put_nowait({"id": identity, "error": "closed"})
                except queue.Full:
                    pass
        self.server.close()
