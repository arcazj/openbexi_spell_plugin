"""Qualification-only logical controller keepalive over the real pinned TLS route."""

from collections import deque
import re
import threading
import time


class HeartbeatController:
    instances = []

    def __init__(self, call):
        self.call = call
        self.lock = threading.RLock()
        self.sessions = {}
        self.started = time.monotonic()
        self.renewals = 0
        self.failures = 0
        self.failure_tail = deque(maxlen=16)
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
                    started = time.monotonic()
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
                        self.renewals += 1
                    except Exception as error:
                        # Evidence must survive loss of the session. Never retain
                        # payloads, nonces, subjects or arbitrary exception text.
                        self.failures += 1
                        code = getattr(error, "code", None)
                        self.failure_tail.append(
                            dict(
                                elapsed_seconds=time.monotonic() - self.started,
                                call_seconds=time.monotonic() - started,
                                overdue_seconds=max(0, started - session["due"]),
                                lease_seconds=session["seconds"],
                                error_type=type(error).__name__,
                                cause_type=type(error.__cause__).__name__,
                                status=getattr(error, "status", None)
                                if type(getattr(error, "status", None)) is int
                                else None,
                                code=code
                                if isinstance(code, str)
                                and re.fullmatch(r"[a-z][a-z_]{0,79}", code)
                                else None,
                            )
                        )
                        self.sessions.pop(connection, None)

    def diagnostics(self):
        with self.lock:
            return dict(
                renewals=self.renewals,
                failures=self.failures,
                active_sessions=len(self.sessions),
                failure_tail=list(self.failure_tail),
            )

    @classmethod
    def close_all(cls):
        for item in cls.instances:
            item.stop.set()
        for item in cls.instances:
            item.thread.join(timeout=6)
        reports = [item.diagnostics() for item in cls.instances]
        cls.instances.clear()
        return reports
