"""Private Context driver seam. Not a launch route or native runtime qualification.

The trusted driver owns sockets and receipt decoding. Every stage reserves two
ledgers before a final live authority check and bounded write. Receipt waits occur
outside this object. No operation, including a failed intent, is replayable.
"""

import fcntl
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from .authority import StartGrant
from .contracts import Fault, canonical
from .mutex import LedgerMutex

STAGES = frozenset({"TRANSPORT", "LOADING", "RELEASE", "ACKNOWLEDGEMENT", "ONBOARD_EXECUTION"})


def provenance(grant):
    fields = asdict(grant)
    token = fields.pop("token")
    fields["token_sha256"] = hashlib.sha256(token.encode("ascii")).hexdigest()
    return canonical(fields).decode()


class DriverGate:
    def __init__(self, authority, directory, bindings, *, capacity=512):
        if getattr(authority, "driver_gate", None) is not None:
            raise ValueError("Context already has a driver gate")
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("Invalid effect capacity")
        self.authority, self.store, self.capacity = authority, authority.store, capacity
        if type(bindings) is not dict or not 1 <= len(bindings) <= 64:
            raise ValueError("Invalid driver bindings")
        self.bindings = {}
        for name, endpoint in bindings.items():
            host, port = endpoint
            ipaddress.IPv4Address(host)  # No DNS rebinding or caller-selected endpoint.
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("Invalid driver endpoint")
            self.bindings[name] = (host, port)
        self.lock, self.failed = LedgerMutex(), False
        self.db = None
        self.guard = None
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.guard = os.fdopen(
                os.open(directory / "driver.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600),
                "a+b",
            )
            fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.db = sqlite3.connect(
                directory / "driver.sqlite3",
                isolation_level=None,
                check_same_thread=False,
                timeout=0.25,
            )
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("CREATE TABLE IF NOT EXISTS identity(context_id TEXT PRIMARY KEY)")
            row = self.db.execute("SELECT context_id FROM identity").fetchone()
            if row and row[0] != self.store.context_id:
                raise ValueError("Driver ledger belongs to another Context")
            self.db.execute("INSERT OR IGNORE INTO identity VALUES(?)", (self.store.context_id,))
            statement = (
                "CREATE TABLE IF NOT EXISTS effect_intents(operation TEXT NOT NULL,stage TEXT NOT NULL,"
                "execution_id TEXT NOT NULL,provenance TEXT NOT NULL,packet_hash TEXT NOT NULL,"
                "state TEXT NOT NULL,receipt_hash TEXT,PRIMARY KEY(operation,stage))"
            )
            with self.store.transaction():
                self.store.db.execute(statement)
                if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 5:
                    self.store.db.execute("PRAGMA user_version=5")
            self.db.execute(statement)
            # Never synthesize a missing receipt across a crash gap.
            self.db.execute(
                "UPDATE effect_intents SET state='UNCERTAIN' WHERE state IN ('INTENT','SENT')"
            )
        except BaseException:
            self.close()
            raise
        authority.driver_gate = self

    @contextmanager
    def _transaction(self):
        with self.lock:
            if self.failed or self.db is None:
                raise Fault(503, "driver_ledger_unavailable")
            try:
                self.db.execute("BEGIN IMMEDIATE")
                yield self.db
                self.db.execute("COMMIT")
            except BaseException as error:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                if isinstance(error, sqlite3.Error):
                    self.failed = True
                raise

    def _live(self, grant, binding):
        if binding not in self.bindings:
            raise Fault(403, "driver_binding_fenced")
        row = self.authority._grant(grant)
        self.authority._require(row["owner"], "execution:start", "execution:control")
        if (
            row["lifecycle"] != "STARTING"
            or json.loads(row["inventory"])["driver_binding"] != binding
        ):
            raise Fault(403, "driver_binding_fenced")

    def send(self, grant, binding, operation, stage, connection, packet, *, deadline=None):
        """Trusted adapter only: actual sendall shares the controller-change mutex."""
        import uuid

        if (
            type(grant) is not StartGrant
            or str(uuid.UUID(operation)) != operation
            or stage not in STAGES
        ):
            raise Fault(400, "invalid_effect_identity")
        if type(packet) is not bytes or not 1 <= len(packet) <= 65536:
            raise Fault(400, "invalid_effect_packet")
        if deadline is not None and (type(deadline) is not float or not math.isfinite(deadline)):
            raise Fault(400, "invalid_effect_deadline")
        if (
            type(connection) is not socket.socket
            or connection.family != socket.AF_INET
            or connection.type != socket.SOCK_STREAM
        ):
            raise Fault(403, "driver_socket_denied")
        if binding not in self.bindings or connection.getpeername() != self.bindings[binding]:
            raise Fault(403, "driver_endpoint_denied")
        values = (
            operation,
            stage,
            grant.execution_id,
            provenance(grant),
            hashlib.sha256(packet).hexdigest(),
        )
        # One ledger writer precedes the execution mutex. No thread may hold
        # the execution mutex while waiting behind another ledger writer. The
        # driver releases this lock before any receipt wait in the transport.
        with self.lock:
            if deadline is not None and time.monotonic() >= deadline:
                raise Fault(503, "effect_deadline_expired")
            # Both durable intents precede final write admission. Ledger work does
            # not authorize effects and must not occupy the short actual-send mutex.
            with self.lock:
                with self.store.transaction():
                    self._live(grant, binding)
                    if self.store.db.execute(
                        "SELECT 1 FROM effect_intents WHERE operation=? AND stage=?",
                        (operation, stage),
                    ).fetchone():
                        raise Fault(409, "effect_replay_denied")
                    if (
                        self.store.db.execute("SELECT COUNT(*) FROM effect_intents").fetchone()[0]
                        >= self.capacity
                    ):
                        raise Fault(503, "effect_capacity_reached")
                    previous = self.store.db.execute(
                        "SELECT execution_id,provenance FROM effect_intents WHERE operation=? LIMIT 1",
                        (operation,),
                    ).fetchone()
                    if previous and (
                        previous["execution_id"] != grant.execution_id
                        or previous["provenance"] != provenance(grant)
                    ):
                        raise Fault(409, "effect_operation_binding_conflict")
                    self.store.db.execute(
                        "INSERT INTO effect_intents VALUES(?,?,?,?,?,'INTENT',NULL)", values
                    )
            uncertainty_recorded = False
            try:
                with self._transaction() as db:
                    if (
                        db.execute("SELECT COUNT(*) FROM effect_intents").fetchone()[0]
                        >= self.capacity
                    ):
                        raise Fault(503, "effect_capacity_reached")
                    db.execute("INSERT INTO effect_intents VALUES(?,?,?,?,?,'INTENT',NULL)", values)
                with self.authority._execution_lock(grant.execution_id):
                    try:
                        with self.store.transaction(write=False):
                            self._live(grant, binding)
                        remaining = (
                            0.2 if deadline is None else min(0.2, deadline - time.monotonic())
                        )
                        if remaining <= 0:
                            raise Fault(503, "effect_deadline_expired")
                        previous_timeout = connection.gettimeout()
                        try:
                            connection.settimeout(remaining)  # Never exceed either deadline.
                            connection.sendall(packet)
                        finally:
                            connection.settimeout(previous_timeout)
                        # Preserve atomic send-to-SENT/error handling before unlocking.
                        with self.lock:
                            with self._transaction() as db:
                                changed = db.execute(
                                    "UPDATE effect_intents SET state='SENT' WHERE operation=? AND stage=? AND state='INTENT'",
                                    (operation, stage),
                                ).rowcount
                                if changed != 1:
                                    raise Fault(409, "effect_ledgers_disagree")
                            with self.store.transaction():
                                changed = self.store.db.execute(
                                    "UPDATE effect_intents SET state='SENT' WHERE operation=? AND stage=? AND state='INTENT'",
                                    (operation, stage),
                                ).rowcount
                                if changed != 1:
                                    raise Fault(409, "effect_ledgers_disagree")
                    except BaseException:
                        # Fence a possible partial write before releasing its mutex.
                        self._uncertain_locked(grant, operation, stage)
                        uncertainty_recorded = True
                        raise
            except BaseException:
                if not uncertainty_recorded:
                    self.uncertain(grant, operation, stage)
                raise

    def _uncertain_locked(self, grant, operation, stage):
        # Caller owns the execution mutex; serialize both ledgers with settlement.
        with self.lock:
            execution_id = grant.execution_id
            with self.store.transaction(write=False):
                original = self.store.db.execute(
                    "SELECT provenance,state FROM effect_intents WHERE operation=? AND stage=? AND execution_id=?",
                    (operation, stage, execution_id),
                ).fetchone()
                # A denied/forged attempt must not fence another live operation or
                # overwrite a previously settled receipt when replay is rejected.
                if (
                    original is None
                    or original["provenance"] != provenance(grant)
                    or original["state"] == "ACKED"
                ):
                    return
            # If persistence itself fails, poison the authority: no further admission.
            try:
                with self._transaction() as db:
                    db.execute(
                        "UPDATE effect_intents SET state='UNCERTAIN' WHERE operation=? AND stage=? AND execution_id=?",
                        (operation, stage, execution_id),
                    )
                with self.store.transaction():
                    self.store.db.execute(
                        "UPDATE effect_intents SET state='UNCERTAIN' WHERE operation=? AND stage=? AND execution_id=?",
                        (operation, stage, execution_id),
                    )
                    self.store.db.execute(
                        "UPDATE executions SET control_state='RECOVERY_REQUIRED',cap_hash=NULL WHERE id=?",
                        (execution_id,),
                    )
                    self.authority._invalidate_claims(execution_id)
            except BaseException:
                self.store.failed = True
                raise

    def settle(self, grant, operation, stage, receipt):
        """Persist a fully decoded, correlated receipt; caller already waited outside locks.

        This private method trusts the driver decoder, never worker-supplied JSON.
        A receipt may arrive after fencing; it cannot restore controller authority.
        """
        if (
            type(grant) is not StartGrant
            or type(receipt) is not bytes
            or not 1 <= len(receipt) <= 65536
        ):
            raise Fault(400, "invalid_effect_receipt")
        receipt_hash = hashlib.sha256(receipt).hexdigest()
        try:
            with self.lock:
                with self.store.transaction(write=False):
                    row = self.store.db.execute(
                        "SELECT * FROM effect_intents WHERE operation=? AND stage=?",
                        (operation, stage),
                    ).fetchone()
                    if (
                        row is None
                        or row["execution_id"] != grant.execution_id
                        or row["provenance"] != provenance(grant)
                        or row["state"] != "SENT"
                    ):
                        raise Fault(409, "effect_receipt_fenced")
                with self._transaction() as db:
                    changed = db.execute(
                        "UPDATE effect_intents SET state='ACKED',receipt_hash=? WHERE operation=? AND stage=? AND state='SENT' AND execution_id=? AND provenance=? AND packet_hash=?",
                        (
                            receipt_hash,
                            operation,
                            stage,
                            grant.execution_id,
                            row["provenance"],
                            row["packet_hash"],
                        ),
                    ).rowcount
                    if changed != 1:
                        raise Fault(409, "effect_ledgers_disagree")
                with self.store.transaction():
                    self.store.db.execute(
                        "UPDATE effect_intents SET state='ACKED',receipt_hash=? WHERE operation=? AND stage=?",
                        (receipt_hash, operation, stage),
                    )
        except BaseException:
            self.uncertain(grant, operation, stage)
            raise

    def uncertain(self, grant, operation, stage):
        try:
            with self.lock:
                with self.authority._execution_lock(grant.execution_id):
                    self._uncertain_locked(grant, operation, stage)
        except BaseException:
            # If we cannot persist/fence an unresolved effect, keep every hold
            # and deny further authority use. A timeout cannot imply safety.
            self.store.failed = True
            raise

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.guard is not None:
            self.guard.close()
            self.guard = None


@dataclass(frozen=True)
class EffectAdmission:
    """Context-created binding passed to the original GPL driver transport."""

    gate: DriverGate
    grant: StartGrant
    binding: str
    operation: str
    deadline: float | None = None

    def validate(self, identity, operation):
        if operation != self.operation or identity.get("procedure") != self.grant.execution_id:
            raise Fault(403, "effect_identity_fenced")
        with self.gate.store.transaction(write=False):
            self.gate._live(self.grant, self.binding)
            row = self.gate.authority._execution(self.grant.execution_id)
            if identity.get("definition") != row["procedure_id"]:
                raise Fault(403, "effect_identity_fenced")

    def send(self, stage, connection, packet):
        return self.gate.send(
            self.grant,
            self.binding,
            self.operation,
            stage,
            connection,
            packet,
            deadline=self.deadline,
        )

    def settle(self, stage, receipt):
        return self.gate.settle(self.grant, self.operation, stage, receipt)

    def uncertain(self, stage):
        return self.gate.uncertain(self.grant, self.operation, stage)
