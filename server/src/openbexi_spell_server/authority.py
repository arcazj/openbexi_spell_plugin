"""Durable prelaunch authority. Native launch, pause, recovery and effects are gated.

Worker methods are private integration points, never RPC routes. A future adapter
must authenticate a uniquely provisioned worker before invoking consume_start.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass

from .contracts import (
    AUTHORITY_MUTATIONS,
    Fault,
    canonical,
    digest,
    fingerprint,
    identifier,
    validate_authority_payload,
)


@dataclass(frozen=True)
class StartGrant:
    authority_incarnation: str
    execution_id: str
    worker_slot: str
    worker_incarnation: str
    worker_generation: int
    control_epoch: int
    connection_id: str
    connection_generation: int
    request_id: str
    operation_digest: str
    token: str


def secret_hash(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class ExecutionAuthority:
    """One instance per ContextStore; policy lookup is live, including on replay."""

    def __init__(self, store, subjects, *, worker_slots=None, clock=time.time):
        self.store, self.subjects, self.clock = store, subjects, clock
        self.mutexes = {}  # Bounded by the retained execution ledger (64).
        self.mutex_guard = threading.Lock()
        self.capacity = 64
        self.reservation_validator = None
        self.start_guard = None
        self.native_pause = None
        self.native_children = None
        if worker_slots is not None and type(worker_slots) is not dict:
            raise ValueError("Worker slots must be an object")
        self.worker_slots = dict(worker_slots or {})
        if len(self.worker_slots) > 10:
            raise ValueError("At most ten single-use worker slots")
        if len(set(self.worker_slots.values())) != len(self.worker_slots):
            raise ValueError("Worker incarnations must be unique")
        for slot, incarnation in self.worker_slots.items():
            identifier(slot)
            identifier(incarnation)
        with store.transaction():
            # CREATE TABLE is transactional, unlike executescript's implicit COMMIT.
            for statement in (
                "CREATE TABLE IF NOT EXISTS sessions("
                "id TEXT PRIMARY KEY,subject TEXT NOT NULL,active INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS session_closures("
                "connection_id TEXT PRIMARY KEY,subject TEXT NOT NULL,key TEXT NOT NULL,hash TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS workers("
                "slot TEXT PRIMARY KEY,incarnation TEXT UNIQUE NOT NULL,spent INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS executions("
                "id TEXT PRIMARY KEY,procedure_id TEXT NOT NULL,inventory TEXT NOT NULL,"
                "worker_slot TEXT UNIQUE NOT NULL,worker_incarnation TEXT NOT NULL,"
                "worker_generation INTEGER NOT NULL,owner TEXT NOT NULL,epoch INTEGER NOT NULL,"
                "connection_id TEXT NOT NULL,connection_generation INTEGER NOT NULL,"
                "cap_hash TEXT, lifecycle TEXT NOT NULL,control_state TEXT NOT NULL,"
                "authority_incarnation TEXT NOT NULL,start_hash TEXT,start_binding TEXT)",
                "CREATE TABLE IF NOT EXISTS reservations("
                "procedure_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS claims("
                "id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,requester TEXT NOT NULL,"
                "connection_id TEXT NOT NULL,expected_owner TEXT NOT NULL,"
                "expected_epoch INTEGER NOT NULL,expires_at REAL NOT NULL,state TEXT NOT NULL)",
                "CREATE UNIQUE INDEX IF NOT EXISTS one_pending_claim ON claims(execution_id) "
                "WHERE state='PENDING'",
                "CREATE TABLE IF NOT EXISTS authority_requests("
                "subject TEXT NOT NULL,scope TEXT NOT NULL,method TEXT NOT NULL,key TEXT NOT NULL,"
                "hash TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(subject,scope,method,key))",
            ):
                store.db.execute(statement)
            if store.db.execute("PRAGMA user_version").fetchone()[0] < 4:
                store.db.execute("PRAGMA user_version=4")
            # Startup never clears logical/worker holds or restores any capability.
            affected = store.db.execute("SELECT id FROM executions").fetchall()
            if affected:
                store.db.execute(
                    "UPDATE executions SET epoch=epoch+1,connection_generation=connection_generation+1,"
                    "cap_hash=NULL,start_hash=NULL,start_binding=NULL,control_state='RECOVERY_REQUIRED',"
                    "lifecycle='RECOVERY_REQUIRED'"
                )
                store.db.execute("UPDATE claims SET state='INVALIDATED' WHERE state='PENDING'")
                store._event("EXECUTIONS_FENCED_ON_STARTUP", {"count": len(affected)})
            store.db.execute("UPDATE sessions SET active=0")
            for slot, incarnation in self.worker_slots.items():
                old = store.db.execute(
                    "SELECT incarnation FROM workers WHERE slot=?", (slot,)
                ).fetchone()
                if old and old[0] != incarnation:
                    raise ValueError(
                        "Worker slot recreation requires separately qualified recovery"
                    )
                if not old:
                    if store.db.execute("SELECT COUNT(*) FROM workers").fetchone()[0] >= 10:
                        raise ValueError("Retained worker slot capacity reached")
                    store.db.execute("INSERT INTO workers VALUES(?,?,0)", (slot, incarnation))
            # A second authority object in one process would otherwise revoke live state.
            if getattr(store, "execution_authority", None) is not None:
                raise ValueError("Context already has an execution authority")
        store.execution_authority = self

    def _require(self, subject, *permissions):
        actor = self.subjects.get(subject)
        if actor is None:
            raise Fault(403, "subject_denied")
        for permission in permissions:
            actor.require(permission)
        return actor

    @contextmanager
    def _execution_lock(self, execution_id):
        # Never create a mutex for an attacker-chosen nonexistent execution.
        with self.store.transaction(write=False):
            self._execution(execution_id)
        with self.mutex_guard:
            lock = self.mutexes.setdefault(execution_id, threading.Lock())
        if not lock.acquire(timeout=0.25):
            raise Fault(503, "execution_busy")
        try:
            yield
        finally:
            lock.release()

    def _execution(self, execution_id):
        row = self.store.db.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone()
        if row is None:
            raise Fault(404, "execution_not_found")
        return row

    def _session(self, subject, connection_id):
        row = self.store.db.execute(
            "SELECT * FROM sessions WHERE id=?", (connection_id,)
        ).fetchone()
        if row is None or row["subject"] != subject or row["active"] != 1:
            raise Fault(403, "connection_denied")

    def _owner(self, subject, payload):
        row = self._execution(payload["execution_id"])
        self._session(subject, payload["connection_id"])
        if (
            row["owner"] != subject
            or row["epoch"] != payload["expected_epoch"]
            or row["connection_id"] != payload["connection_id"]
            or row["connection_generation"] != payload["connection_generation"]
            or row["control_state"] != "OWNED"
            or row["authority_incarnation"] != self.store.incarnation
            or not row["cap_hash"]
            or not hmac.compare_digest(row["cap_hash"], secret_hash(payload["capability"]))
        ):
            raise Fault(403, "controller_fenced")
        return row

    def _replay(self, subject, method, key, payload):
        row = self.store.db.execute(
            "SELECT hash,result FROM authority_requests WHERE subject=? AND scope=? AND method=? AND key=?",
            (subject, payload.get("execution_id", "context"), method, key),
        ).fetchone()
        if row:
            if row["hash"] != digest(payload):
                raise Fault(409, "idempotency_payload_conflict")
            result = json.loads(row["result"])
            result["replayed"] = True
            return result
        if (
            self.store.db.execute("SELECT COUNT(*) FROM authority_requests").fetchone()[0]
            >= self.store.max_idempotency
        ):
            raise Fault(503, "idempotency_capacity_reached")
        return None

    def _record(self, subject, method, key, payload, result):
        # Only hashes of capability inputs, and never plaintext capability outputs.
        durable = {k: v for k, v in result.items() if k != "capability"}
        if "capability" in result:
            durable["capability_delivery"] = "rebind_required_on_replay"
        self.store.db.execute(
            "INSERT INTO authority_requests VALUES(?,?,?,?,?,?)",
            (
                subject,
                payload.get("execution_id", "context"),
                method,
                key,
                digest(payload),
                canonical(durable).decode(),
            ),
        )
        return result

    def _invalidate_claims(self, execution_id):
        self.store.db.execute(
            "UPDATE claims SET state='INVALIDATED' WHERE execution_id=? AND state='PENDING'",
            (execution_id,),
        )

    def _expire_claim(self, execution_id):
        rows = self.store.db.execute(
            "SELECT id FROM claims WHERE execution_id=? AND state='PENDING' AND expires_at<=?",
            (execution_id, self.clock()),
        ).fetchall()
        for row in rows:
            self.store.db.execute("UPDATE claims SET state='EXPIRED' WHERE id=?", (row[0],))
            self.store._event(
                "CONTROL_CLAIM_EXPIRED", {"claim_id": row[0], "execution_id": execution_id}
            )

    def list_executions(self, subject):
        self._require(subject, "execution:read")
        if self.native_pause is not None:
            self.native_pause.expire()
        with self.store.transaction(write=False):
            executions = []
            for row in self.store.db.execute("SELECT * FROM executions ORDER BY id"):
                item = self._public(row)
                claim = self.store.db.execute(
                    "SELECT id,requester,expires_at FROM claims WHERE execution_id=? AND state='PENDING'",
                    (row["id"],),
                ).fetchone()
                item["pending_claim"] = (
                    dict(claim) if claim and claim["expires_at"] > self.clock() else None
                )
                if self.native_pause is not None:
                    item["pause_barrier"] = self.native_pause.snapshot(row["id"])
                executions.append(item)
            return {"executions": executions, "runtime_enabled": False}

    @staticmethod
    def _public(row):
        return {
            key: row[key]
            for key in (
                "id",
                "procedure_id",
                "owner",
                "epoch",
                "connection_generation",
                "lifecycle",
                "control_state",
            )
        }

    def mutate(self, subject, method, key, payload):
        """No caller can bypass validation or live policy through a local adapter."""
        if method not in AUTHORITY_MUTATIONS:
            raise Fault(404, "method_not_available")
        identifier(key)
        validate_authority_payload(method, payload)
        permissions = {
            "session.open": ("execution:control",),
            "session.close": ("execution:control",),
            "execution.reserve": ("execution:start", "execution:control"),
            "execution.rebind": ("execution:control",),
            "execution.claim": ("execution:request_control", "execution:control"),
            "execution.decide": ("execution:control",),
            "execution.cancel": ("execution:request_control",),
        }
        self._require(subject, *permissions[method])
        if method == "session.close":
            return self._close_session(subject, key, payload)
        if method in ("session.open", "execution.reserve"):
            with self.store.transaction():
                self._require(subject, *permissions[method])
                return self._mutate(subject, method, key, payload)
        with self._execution_lock(payload["execution_id"]):
            with self.store.transaction():
                self._require(subject, *permissions[method])
                return self._mutate(subject, method, key, payload)

    def _close_session(self, subject, key, payload):
        """Close admission before serializing final fencing with execution writes.

        CLOSING (active=2) survives timeout/crash and never admits new work. No
        SQLite transaction is held while waiting for any execution mutex. Only
        the original close request may finish a partially completed close.
        """
        connection = payload["connection_id"]
        with self.store.transaction():
            self._require(subject, "execution:control")
            replay = self._replay(subject, "session.close", key, payload)
            if replay is not None:
                return replay
            pending = self.store.db.execute(
                "SELECT * FROM session_closures WHERE connection_id=?", (connection,)
            ).fetchone()
            if pending is None:
                self._session(subject, connection)
                self.store.db.execute(
                    "INSERT INTO session_closures VALUES(?,?,?,?)",
                    (connection, subject, key, digest(payload)),
                )
                self.store.db.execute("UPDATE sessions SET active=2 WHERE id=?", (connection,))
                self.store._event(
                    "CONTROL_CONNECTION_CLOSING", {"connection_id": connection, "subject": subject}
                )
            elif (
                pending["subject"] != subject
                or pending["key"] != key
                or pending["hash"] != digest(payload)
            ):
                raise Fault(409, "connection_close_pending")
            executions = self.store.db.execute(
                "SELECT id FROM executions WHERE owner=? AND connection_id=? ORDER BY id",
                (subject, connection),
            ).fetchall()
        with ExitStack() as locks:
            for execution in executions:
                locks.enter_context(self._execution_lock(execution["id"]))
            with self.store.transaction():
                self._require(subject, "execution:control")
                replay = self._replay(subject, "session.close", key, payload)
                if replay is not None:
                    return replay
                self.store.db.execute("UPDATE sessions SET active=0 WHERE id=?", (connection,))
                # A concurrent rebind away from this closing connection wins.
                rows = self.store.db.execute(
                    "SELECT id FROM executions WHERE owner=? AND connection_id=? AND control_state='OWNED'",
                    (subject, connection),
                ).fetchall()
                for row in rows:
                    self.store.db.execute(
                        "UPDATE executions SET control_state='CONTROLLER_DISCONNECTED',cap_hash=NULL WHERE id=?",
                        (row["id"],),
                    )
                    self._invalidate_claims(row["id"])
                self.store._event(
                    "CONTROL_CONNECTION_CLOSED",
                    {
                        "connection_id": connection,
                        "subject": subject,
                        "fenced_executions": len(rows),
                    },
                )
                return self._record(subject, "session.close", key, payload, {"closed": True})

    def _mutate(self, subject, method, key, payload):
        # A close/accept replay can be returned after its connection was invalidated;
        # only the authenticated original subject can obtain the redacted decision.
        result: dict
        replay = self._replay(subject, method, key, payload)
        if replay is not None:
            return replay
        if method == "session.open":
            if self.store.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] >= 128:
                raise Fault(503, "session_capacity_reached")
            if (
                self.store.db.execute(
                    "SELECT COUNT(*) FROM sessions WHERE subject=?", (subject,)
                ).fetchone()[0]
                >= 16
            ):
                raise Fault(503, "subject_session_capacity_reached")
            connection = str(uuid.uuid4())
            self.store.db.execute("INSERT INTO sessions VALUES(?,?,1)", (connection, subject))
            self.store._event(
                "CONTROL_CONNECTION_OPENED", {"connection_id": connection, "subject": subject}
            )
            result = {"connection_id": connection}
        elif method == "execution.reserve":
            result = self._reserve(subject, payload)
        elif method == "execution.rebind":
            result = self._rebind(subject, payload)
        elif method == "execution.claim":
            result = self._claim(subject, payload)
        elif method == "execution.decide":
            result = self._decide(subject, payload)
        else:
            result = self._cancel(subject, payload)
        return self._record(subject, method, key, payload, result)

    def _reserve(self, subject, payload):
        if self.reservation_validator is not None:
            payload = self.reservation_validator(payload)
        self._session(subject, payload["connection_id"])
        if self.store.db.execute("SELECT COUNT(*) FROM executions").fetchone()[0] >= self.capacity:
            raise Fault(503, "execution_capacity_reached")
        if self.store.db.execute(
            "SELECT 1 FROM reservations WHERE procedure_id=?", (payload["procedure_id"],)
        ).fetchone():
            raise Fault(409, "procedure_reserved")
        worker = next(
            (
                row
                for row in self.store.db.execute(
                    "SELECT * FROM workers WHERE spent=0 AND slot NOT IN (SELECT worker_slot FROM executions) ORDER BY slot"
                )
                if self.worker_slots.get(row["slot"]) == row["incarnation"]
            ),
            None,
        )
        if worker is None:
            raise Fault(503, "worker_capacity_unavailable")
        execution_id, capability = str(uuid.uuid4()), secrets.token_hex(32)
        inventory = {
            k: payload[k]
            for k in ("source_revision", "source_sha256", "runtime_image", "driver_binding")
        }
        self.store.db.execute(
            "INSERT INTO executions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                execution_id,
                payload["procedure_id"],
                canonical(inventory).decode(),
                worker["slot"],
                worker["incarnation"],
                1,
                subject,
                1,
                payload["connection_id"],
                1,
                secret_hash(capability),
                "RESERVED",
                "OWNED",
                self.store.incarnation,
                None,
                None,
            ),
        )
        self.store.db.execute(
            "INSERT INTO reservations VALUES(?,?)", (payload["procedure_id"], execution_id)
        )
        self.store._event(
            "EXECUTION_RESERVED",
            {
                "execution_id": execution_id,
                "procedure_id": payload["procedure_id"],
                "subject": subject,
                "worker_slot": worker["slot"],
            },
        )
        return {
            **self._public(self._execution(execution_id)),
            "capability": capability,
            "connection_id": payload["connection_id"],
            "runtime_enabled": False,
        }

    def _rebind(self, subject, payload):
        self._session(subject, payload["connection_id"])
        row = self._execution(payload["execution_id"])
        if row["owner"] != subject or row["epoch"] != payload["expected_epoch"]:
            raise Fault(403, "controller_fenced")
        # Native resumption/rebinding needs a qualified quiescence barrier. Stay closed.
        if row["lifecycle"] != "RESERVED" or row["authority_incarnation"] != self.store.incarnation:
            raise Fault(409, "native_rebind_unqualified")
        capability = secrets.token_hex(32)
        self.store.db.execute(
            "UPDATE executions SET connection_id=?,connection_generation=connection_generation+1,cap_hash=?,start_hash=NULL,start_binding=NULL,control_state='OWNED' WHERE id=?",
            (payload["connection_id"], secret_hash(capability), row["id"]),
        )
        self._invalidate_claims(row["id"])
        self.store._event("CONTROLLER_REBOUND", {"execution_id": row["id"], "subject": subject})
        return {
            **self._public(self._execution(row["id"])),
            "capability": capability,
            "connection_id": payload["connection_id"],
        }

    def _claim(self, subject, payload):
        self._session(subject, payload["connection_id"])
        row = self._execution(payload["execution_id"])
        if row["owner"] == subject:
            raise Fault(409, "already_owner")
        if row["control_state"] != "OWNED" or row["epoch"] != payload["expected_epoch"]:
            raise Fault(409, "claim_epoch_conflict")
        self._expire_claim(row["id"])
        if self.store.db.execute(
            "SELECT 1 FROM claims WHERE execution_id=? AND state='PENDING'", (row["id"],)
        ).fetchone():
            raise Fault(409, "claim_pending")
        if self.store.db.execute("SELECT COUNT(*) FROM claims").fetchone()[0] >= self.capacity * 4:
            raise Fault(503, "claim_capacity_reached")
        claim_id = str(uuid.uuid4())
        expires_at = self.clock() + 60
        self.store.db.execute(
            "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)",
            (
                claim_id,
                row["id"],
                subject,
                payload["connection_id"],
                row["owner"],
                row["epoch"],
                expires_at,
                "PENDING",
            ),
        )
        self.store._event(
            "CONTROL_CLAIM_REQUESTED",
            {"execution_id": row["id"], "claim_id": claim_id, "requester": subject},
        )
        return {"claim_id": claim_id, "state": "PENDING", "expires_at": expires_at}

    def _pending(self, payload):
        claim = self.store.db.execute(
            "SELECT * FROM claims WHERE id=? AND execution_id=?",
            (payload["claim_id"], payload["execution_id"]),
        ).fetchone()
        if claim is None or claim["state"] != "PENDING":
            raise Fault(409, "claim_not_pending")
        return claim

    def _decide(self, subject, payload):
        row = self._owner(subject, payload)
        claim = self._pending(payload)
        if claim["expires_at"] <= self.clock():
            # Return a durable expiry decision, rather than rolling it back by raising.
            self._expire_claim(row["id"])
            return {"claim_id": claim["id"], "state": "EXPIRED"}
        if claim["expected_owner"] != subject or claim["expected_epoch"] != row["epoch"]:
            raise Fault(409, "claim_epoch_conflict")
        if payload["decision"] == "reject":
            self.store.db.execute("UPDATE claims SET state='REJECTED' WHERE id=?", (claim["id"],))
            self.store._event(
                "CONTROL_CLAIM_REJECTED", {"execution_id": row["id"], "claim_id": claim["id"]}
            )
            return {"claim_id": claim["id"], "state": "REJECTED"}
        self._require(claim["requester"], "execution:request_control", "execution:control")
        self._session(claim["requester"], claim["connection_id"])
        if row["lifecycle"] != "RESERVED":
            if self.native_pause is not None and row["lifecycle"] == "STARTING":
                return self.native_pause.begin(row, claim)
            # A start grant is a possible external effect. No fake native pause proof.
            self.store.db.execute(
                "UPDATE executions SET control_state='RECOVERY_REQUIRED',cap_hash=NULL WHERE id=?",
                (row["id"],),
            )
            self._invalidate_claims(row["id"])
            self.store._event(
                "CONTROL_TRANSFER_BLOCKED",
                {"execution_id": row["id"], "reason": "native_quiescence_unqualified"},
            )
            return {"claim_id": claim["id"], "state": "BLOCKED", "recovery_required": True}
        self.store.db.execute(
            "UPDATE executions SET owner=?,epoch=epoch+1,connection_id=?,connection_generation=connection_generation+1,cap_hash=NULL,start_hash=NULL,start_binding=NULL WHERE id=?",
            (claim["requester"], claim["connection_id"], row["id"]),
        )
        self.store.db.execute("UPDATE claims SET state='ACCEPTED' WHERE id=?", (claim["id"],))
        self.store._event(
            "CONTROL_CLAIM_ACCEPTED", {"execution_id": row["id"], "claim_id": claim["id"]}
        )
        self.store._event(
            "CONTROL_OWNER_CHANGED",
            {"execution_id": row["id"], "owner": claim["requester"], "epoch": row["epoch"] + 1},
        )
        return {
            "claim_id": claim["id"],
            "state": "ACCEPTED",
            "epoch": row["epoch"] + 1,
            "capability_delivery": "new_owner_must_rebind",
        }

    def _cancel(self, subject, payload):
        self._session(subject, payload["connection_id"])
        claim = self._pending(payload)
        if claim["requester"] != subject or claim["connection_id"] != payload["connection_id"]:
            raise Fault(403, "claim_requester_required")
        if claim["expires_at"] <= self.clock():
            self._expire_claim(payload["execution_id"])
            return {"claim_id": claim["id"], "state": "EXPIRED"}
        self.store.db.execute("UPDATE claims SET state='CANCELLED' WHERE id=?", (claim["id"],))
        self.store._event(
            "CONTROL_CLAIM_CANCELLED",
            {"execution_id": payload["execution_id"], "claim_id": claim["id"]},
        )
        return {"claim_id": claim["id"], "state": "CANCELLED"}

    def admit_start(self, subject, payload):
        """Private controller-to-adapter seam; no launch RPC until source/worker integration.

        Issue original provenance on the authenticated controller's operation,
        before any worker request. The worker never selects a new current epoch.
        """
        validate_authority_payload("execution.start", payload)
        self._require(subject, "execution:start", "execution:control")
        with self._execution_lock(payload["execution_id"]):
            with self.store.transaction():
                self._require(subject, "execution:start", "execution:control")
                row = self._owner(subject, payload)
                if row["lifecycle"] != "RESERVED" or row["start_hash"]:
                    raise Fault(403, "worker_start_fenced")
                if self.worker_slots.get(row["worker_slot"]) != row["worker_incarnation"]:
                    raise Fault(403, "worker_start_fenced")
                if self.start_guard is not None:
                    self.start_guard(row)
                grant = StartGrant(
                    self.store.incarnation,
                    row["id"],
                    row["worker_slot"],
                    row["worker_incarnation"],
                    row["worker_generation"],
                    row["epoch"],
                    row["connection_id"],
                    row["connection_generation"],
                    str(uuid.uuid4()),
                    digest(json.loads(row["inventory"])),
                    secrets.token_hex(32),
                )
                fields = asdict(grant)
                token = fields.pop("token")
                self.store.db.execute(
                    "UPDATE executions SET start_hash=?,start_binding=? WHERE id=?",
                    (secret_hash(token), canonical(fields).decode(), row["id"]),
                )
                self.store._event(
                    "WORKER_START_ADMITTED",
                    {
                        "execution_id": row["id"],
                        "request_id": grant.request_id,
                        "epoch": row["epoch"],
                        "subject": subject,
                    },
                )
                return grant

    def _original_grant(self, grant):
        """Immutable consumed identity, never permission for a new effect.

        Only the fenced pause/report safety route may use this without live
        controller authority. Driver/control paths must continue using _grant.
        """
        if type(grant) is not StartGrant:
            raise Fault(403, "worker_grant_fenced")
        try:
            fingerprint(grant.token)
        except Fault as error:
            raise Fault(403, "worker_grant_fenced") from error
        row = self._execution(grant.execution_id)
        fields = asdict(grant)
        token = fields.pop("token")
        if (
            row["authority_incarnation"] != self.store.incarnation
            or grant.authority_incarnation != self.store.incarnation
            or row["epoch"] != grant.control_epoch
            or row["connection_id"] != grant.connection_id
            or row["connection_generation"] != grant.connection_generation
            or not row["start_hash"]
            or not hmac.compare_digest(row["start_hash"], secret_hash(token))
            or row["start_binding"] != canonical(fields).decode()
        ):
            raise Fault(403, "worker_grant_fenced")
        return row

    def _grant(self, grant):
        # Preserve the existing effect path's live-policy/session precedence.
        # The safety-only reporter deliberately does not enter this path.
        if type(grant) is not StartGrant:
            raise Fault(403, "worker_grant_fenced")
        try:
            fingerprint(grant.token)
        except Fault as error:
            raise Fault(403, "worker_grant_fenced") from error
        row = self._execution(grant.execution_id)
        self._require(row["owner"], "execution:start", "execution:control")
        self._session(row["owner"], row["connection_id"])
        if row["control_state"] != "OWNED" or not row["cap_hash"]:
            raise Fault(403, "worker_grant_fenced")
        return self._original_grant(grant)

    def consume_start(
        self, grant, authenticated_slot, authenticated_incarnation, *, consumption_hash=None
    ):
        """Trusted adapter only: authenticate worker incarnation BEFORE calling.

        Consume exactly the previously admitted immutable grant. Response loss
        retains the spent slot and reservation. This method cannot issue a grant.
        """
        if type(grant) is not StartGrant:
            raise Fault(403, "worker_grant_fenced")
        if consumption_hash is not None:
            fingerprint(consumption_hash)
        with self._execution_lock(grant.execution_id):
            with self.store.transaction():
                row = self._grant(grant)
                if (
                    row["worker_slot"] != authenticated_slot
                    or row["worker_incarnation"] != authenticated_incarnation
                    or self.worker_slots.get(authenticated_slot) != authenticated_incarnation
                    or row["lifecycle"] != "RESERVED"
                ):
                    raise Fault(403, "worker_start_fenced")
                changed = self.store.db.execute(
                    "UPDATE workers SET spent=1 WHERE slot=? AND incarnation=? AND spent=0",
                    (authenticated_slot, authenticated_incarnation),
                ).rowcount
                if changed != 1:
                    raise Fault(409, "worker_already_spent")
                if self.start_guard is not None:
                    self.start_guard(row)
                self.store.db.execute(
                    "UPDATE executions SET lifecycle='STARTING' WHERE id=?",
                    (row["id"],),
                )
                if consumption_hash is not None:
                    self.store.db.execute(
                        "INSERT INTO worker_runtime_receipts VALUES(?,?,?)",
                        (grant.execution_id, grant.request_id, consumption_hash),
                    )
                self.store._event(
                    "WORKER_START_CONSUMED",
                    {
                        "execution_id": row["id"],
                        "worker_slot": authenticated_slot,
                        "request_id": grant.request_id,
                    },
                )
                return True

    def validate_start_grant(self, grant):
        """Recheck ORIGINAL provenance after consumption; this admits no driver effect."""
        if type(grant) is not StartGrant:
            raise Fault(403, "worker_grant_fenced")
        with self._execution_lock(grant.execution_id):
            with self.store.transaction(write=False):
                row = self._grant(grant)
                if row["lifecycle"] != "STARTING":
                    raise Fault(403, "worker_grant_fenced")
                return True
