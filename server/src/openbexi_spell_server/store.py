"""Linux single-process authority state. No SQLite transaction contains network I/O."""

import fcntl
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from contextlib import contextmanager

from .contracts import Fault, canonical, digest, identifier


class ContextStore:
    def __init__(
        self, directory, context_id, *, max_keys=64, max_events=10000, max_idempotency=10000
    ):
        self.context_id = identifier(context_id)
        if any(type(n) is not int or n < 1 for n in (max_keys, max_events, max_idempotency)):
            raise ValueError("Invalid state limits")
        if max_keys > 64 or max_events > 100000 or max_idempotency > 100000:
            raise ValueError("State limits exceed supported profile")
        self.max_keys, self.max_events, self.max_idempotency = max_keys, max_events, max_idempotency
        self.lock, self.failed, self.closed = threading.RLock(), False, False
        self.db: sqlite3.Connection
        self.guard = None
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            fd = os.open(
                directory / "authority.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            self.guard = os.fdopen(fd, "a+b")
            fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.db = sqlite3.connect(
                directory / "context.sqlite3",
                timeout=0.25,
                isolation_level=None,
                check_same_thread=False,
            )
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA synchronous=FULL")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
                raise ValueError("Unsupported authority schema")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS blackboard(
                    key TEXT PRIMARY KEY,revision INTEGER NOT NULL,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT NOT NULL,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS idempotency(
                    subject TEXT NOT NULL,key TEXT NOT NULL,hash TEXT NOT NULL,result TEXT NOT NULL,
                    PRIMARY KEY(subject,key));

            """)
            if version == 0:
                self.db.execute("PRAGMA user_version=1")
            self.incarnation = str(uuid.uuid4())
            with self.transaction():
                row = self.db.execute("SELECT value FROM meta WHERE name='context_id'").fetchone()
                if row and row[0] != context_id:
                    raise ValueError("State directory belongs to a different Context")
                self.db.execute("INSERT OR IGNORE INTO meta VALUES('context_id',?)", (context_id,))
                self.db.execute(
                    "INSERT INTO meta VALUES('incarnation',?) "
                    "ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                    (self.incarnation,),
                )
                self._event("CONTEXT_STARTED", {"incarnation": self.incarnation})
        except BaseException:
            self.close()
            raise

    @contextmanager
    def transaction(self, *, write=True):
        with self.lock:
            if self.closed or self.failed:
                raise Fault(503, "state_unavailable")
            try:
                self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield
                self.db.execute("COMMIT")
            except BaseException as error:
                try:
                    if self.db.in_transaction:
                        self.db.execute("ROLLBACK")
                except sqlite3.Error:
                    self.failed = True
                if isinstance(error, sqlite3.Error):
                    self.failed = True
                    raise Fault(503, "state_unavailable") from error
                raise

    def _event(self, kind, body):
        count = self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if count >= self.max_events:
            raise Fault(503, "audit_capacity_reached")
        return self.db.execute(
            "INSERT INTO events(type,body) VALUES(?,?)", (kind, canonical(body).decode())
        ).lastrowid

    def snapshot(self, *, values=True):
        with self.transaction(write=False):
            sequence = self.db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
            rows = self.db.execute(
                "SELECT key,revision,value FROM blackboard ORDER BY key"
            ).fetchall()
            result = dict(
                context_id=self.context_id,
                incarnation=self.incarnation,
                sequence=sequence,
                runtime_enabled=False,
            )
            if values:
                result["blackboard"] = {
                    r["key"]: dict(revision=r["revision"], value=json.loads(r["value"]))
                    for r in rows
                }
            else:
                result["blackboard_revisions"] = {r["key"]: r["revision"] for r in rows}
            return result

    def cas(self, subject, key, payload):
        """Called only after live ACL checks; key is scoped to subject/blackboard.cas."""
        payload_hash = digest(payload)
        with self.transaction():
            row = self.db.execute(
                "SELECT hash,result FROM idempotency WHERE subject=? AND key=?", (subject, key)
            ).fetchone()
            if row:
                if row["hash"] != payload_hash:
                    raise Fault(409, "idempotency_payload_conflict")
                return json.loads(row["result"])
            count = self.db.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0]
            if count >= self.max_idempotency:
                raise Fault(503, "idempotency_capacity_reached")
            name = payload["key"]
            current = self.db.execute(
                "SELECT revision FROM blackboard WHERE key=?", (name,)
            ).fetchone()
            revision = current[0] if current else 0
            if revision != payload["expected_revision"]:
                raise Fault(409, "blackboard_revision_conflict")
            if not current:
                count = self.db.execute("SELECT COUNT(*) FROM blackboard").fetchone()[0]
                if count >= self.max_keys:
                    raise Fault(503, "blackboard_capacity_reached")
            raw = canonical(payload["value"]).decode()
            # Preserve a complete bounded response, not just a per-value limit.
            total = self.db.execute(
                "SELECT COALESCE(SUM(length(value)),0) FROM blackboard"
            ).fetchone()[0]
            old = self.db.execute(
                "SELECT length(value) FROM blackboard WHERE key=?", (name,)
            ).fetchone()
            if total - (old[0] if old else 0) + len(raw) > 32768:
                raise Fault(503, "blackboard_byte_capacity_reached")
            self.db.execute(
                "INSERT INTO blackboard VALUES(?,?,?) ON CONFLICT(key) DO UPDATE "
                "SET revision=excluded.revision,value=excluded.value",
                (name, revision + 1, raw),
            )
            sequence = self._event(
                "BLACKBOARD_CHANGED", dict(key=name, revision=revision + 1, subject=subject)
            )
            result = dict(
                context_id=self.context_id, key=name, revision=revision + 1, sequence=sequence
            )
            self.db.execute(
                "INSERT INTO idempotency VALUES(?,?,?,?)",
                (subject, key, payload_hash, canonical(result).decode()),
            )
            return result

    def close(self):
        with self.lock:
            self.closed = True
            database = getattr(self, "db", None)
            if database is not None:
                database.close()
            if self.guard is not None:
                self.guard.close()
                self.guard = None
