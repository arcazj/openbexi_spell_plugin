"""Monotonic, one-challenge-at-a-time controller leases; never a pause proof."""

import hmac
import secrets
import threading
import time

from .contracts import Fault


class ControllerLiveness:
    def __init__(self, authority, seconds, *, clock=time.monotonic):
        if type(seconds) is not int or not 5 <= seconds <= 300:
            raise ValueError("Controller lease must be an integer from 5 to 300 seconds")
        self.authority, self.store = authority, authority.store
        self.seconds, self.clock = seconds, clock
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS controller_leases("
                "connection_id TEXT PRIMARY KEY,deadline REAL NOT NULL,nonce_hash TEXT NOT NULL,"
                "expired INTEGER NOT NULL DEFAULT 0)"
            )
            self.store.db.execute("PRAGMA user_version=23")

    def open(self, connection):
        from .authority import secret_hash

        nonce = secrets.token_hex(32)
        self.store.db.execute(
            "INSERT INTO controller_leases VALUES(?,?,?,0)",
            (connection, self.clock() + self.seconds, secret_hash(nonce)),
        )
        return {"heartbeat_nonce": nonce, "lease_seconds": self.seconds}

    def require(self, connection):
        row = self.store.db.execute(
            "SELECT * FROM controller_leases WHERE connection_id=?", (connection,)
        ).fetchone()
        if row is None or row["expired"] or self.clock() >= row["deadline"]:
            raise Fault(403, "controller_lease_expired")
        return row

    def heartbeat(self, subject, payload):
        from .authority import secret_hash

        connection = payload["connection_id"]
        with self.store.transaction():
            self.authority._require(subject, "execution:control")
            self.authority._session(subject, connection)
            row = self.require(connection)
            if not hmac.compare_digest(row["nonce_hash"], secret_hash(payload["heartbeat_nonce"])):
                raise Fault(403, "heartbeat_challenge_denied")
            # No replay extends a lease. A lost reply requires explicit recovery;
            # only the next delivered challenge can renew again. No per-beat
            # audit/idempotency rows accumulate and no secret is stored in clear.
            nonce = secrets.token_hex(32)
            self.store.db.execute(
                "UPDATE controller_leases SET deadline=?,nonce_hash=? WHERE connection_id=?",
                (self.clock() + self.seconds, secret_hash(nonce), connection),
            )
            return {"heartbeat_nonce": nonce, "lease_seconds": self.seconds}

    def expire(self):
        # Close admission for ALL overdue sessions before waiting for any
        # execution. _session also checks the deadline at every admission/write.
        with self.store.transaction():
            rows = self.store.db.execute(
                "SELECT l.connection_id,s.subject FROM controller_leases l "
                "JOIN sessions s ON s.id=l.connection_id "
                "WHERE l.deadline<=? AND l.expired=0 AND s.active=1",
                (self.clock(),),
            ).fetchall()
            for row in rows:
                self.store.db.execute(
                    "UPDATE sessions SET active=2 WHERE id=?", (row["connection_id"],)
                )
                self.store.db.execute(
                    "UPDATE controller_leases SET expired=1 WHERE connection_id=?",
                    (row["connection_id"],),
                )
                self.store._event("CONTROL_CONNECTION_CLOSING", dict(row, cause="lease_expired"))
            pending = self.store.db.execute(
                "SELECT s.id,s.subject FROM sessions s JOIN controller_leases l "
                "ON l.connection_id=s.id WHERE l.expired=1 AND s.active=2"
            ).fetchall()
        for session in pending:
            if self.stop.is_set():
                return
            with self.store.transaction(write=False):
                executions = self.store.db.execute(
                    "SELECT id FROM executions WHERE connection_id=? AND control_state='OWNED'",
                    (session["id"],),
                ).fetchall()
            for execution in executions:
                if self.stop.is_set():
                    return
                try:
                    with self.authority._execution_lock(execution["id"]):
                        with self.store.transaction():
                            # A rebind to a new connection wins over late cleanup.
                            row = self.authority._execution(execution["id"])
                            if (
                                row["connection_id"] == session["id"]
                                and row["control_state"] == "OWNED"
                            ):
                                self.store.db.execute(
                                    "UPDATE executions SET control_state='CONTROLLER_DISCONNECTED',"
                                    "cap_hash=NULL WHERE id=?",
                                    (row["id"],),
                                )
                                self.authority._invalidate_claims(row["id"])
                except Fault as error:
                    if error.code != "execution_busy":
                        raise
            with self.store.transaction():
                if not self.store.db.execute(
                    "SELECT 1 FROM executions WHERE connection_id=? AND control_state='OWNED'",
                    (session["id"],),
                ).fetchone():
                    self.store.db.execute(
                        "UPDATE sessions SET active=0 WHERE id=?", (session["id"],)
                    )
                    self.store._event(
                        "CONTROL_CONNECTION_CLOSED",
                        {
                            "connection_id": session["id"],
                            "subject": session["subject"],
                            "cause": "lease_expired",
                        },
                    )

    def start(self):
        if self.thread is not None:
            raise ValueError("Controller watchdog already started")

        def watch():
            while not self.stop.wait(0.1):
                try:
                    self.expire()
                except Exception:
                    # Audit/storage failure cannot silently leave a healthy
                    # authority accepting writes without its durable fence.
                    with self.store.lock:
                        self.store.failed = True
                    return

        self.thread = threading.Thread(target=watch, name="controller-liveness", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=1)
