"""Qualification-only logical controller keepalive over the real pinned TLS route."""

import threading
import time


class HeartbeatController:
    instances = []

    def __init__(self, call):
        self.call = call
        self.lock = threading.RLock()
        self.sessions = {}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.instances.append(self)
        self.thread.start()

    def __call__(self, method, payload, subject="alice"):
        result = self.call(method, payload, subject)
        with self.lock:
            if method == "session.open" and "heartbeat_nonce" in result:
                self.sessions[result["connection_id"]] = dict(
                    subject=subject,
                    nonce=result["heartbeat_nonce"],
                    seconds=result["lease_seconds"],
                    due=time.monotonic() + result["lease_seconds"] / 3,
                )
            elif method == "session.close":
                self.sessions.pop(payload["connection_id"], None)
        return result

    def lose(self, connection):
        """Inject absent heartbeats; no close RPC, pause, retry or recovery."""
        with self.lock:
            session = self.sessions.pop(connection)
            return {
                "fault": "heartbeat_transport_detached",
                "lease_seconds": session["seconds"],
            }

    def _run(self):
        while not self.stop.wait(0.1):
            with self.lock:
                # Serialize detach with a bounded in-flight renewal, so the
                # recorded loss time cannot precede a later successful beat.
                for connection, session in list(self.sessions.items()):
                    if session["due"] > time.monotonic():
                        continue
                    try:
                        result = self.call(
                            "session.heartbeat",
                            dict(
                                connection_id=connection,
                                heartbeat_nonce=session["nonce"],
                            ),
                            session["subject"],
                        )
                        session.update(
                            nonce=result["heartbeat_nonce"],
                            due=time.monotonic() + result["lease_seconds"] / 3,
                        )
                    except Exception:
                        self.sessions.pop(connection, None)

    @classmethod
    def close_all(cls):
        for item in cls.instances:
            item.stop.set()
        for item in cls.instances:
            item.thread.join(timeout=6)
        cls.instances.clear()
