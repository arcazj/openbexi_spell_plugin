"""Durable, single-attempt native RUN journal; never queue-settlement proof.

The private retained profile permits one agent RUN per admitted native member.
Commit uncertainty before IPC. Even a send acknowledgment leaves that command
unproven: the frozen mailbox can discard it, and this journal is not a native
dequeue fence. No row authorizes handoff, replay, resume or reservation release.
"""

from .contracts import Fault, digest
from .family import FamilyAdmission
from .preflight import canonical_uuid


class NativeControlJournal:
    def __init__(self, authority):
        self.authority, self.store = authority, authority.store
        if authority.native_controls is not None:
            raise ValueError("Context already has a native control journal")
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_control_attempts("
                "request_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,target_id TEXT NOT NULL,"
                "origin_hash TEXT NOT NULL,operation_digest TEXT NOT NULL,"
                "command TEXT NOT NULL,state TEXT NOT NULL,outcome TEXT,"
                "UNIQUE(execution_id,target_id))"
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 11:
                self.store.db.execute("PRAGMA user_version=11")
            self.store.db.execute(
                "UPDATE native_control_attempts SET state='RESTART_FENCED'"
                " WHERE state!='RESTART_FENCED'"
            )
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_control_forwards("
                "request_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,origin_hash TEXT NOT NULL,"
                "operation_digest TEXT NOT NULL,state TEXT NOT NULL)"
            )
            self.store.db.execute("UPDATE native_control_forwards SET state='RESTART_FENCED'")
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 12:
                self.store.db.execute("PRAGMA user_version=12")
        authority.native_controls = self

    @staticmethod
    def operation(body):
        canonical_uuid(body["request_id"])
        if body["target_admission_id"] is not None:
            canonical_uuid(body["target_admission_id"])
        if type(body["command"]) is not str or body["command"] != "CMD_RUN":
            raise Fault(403, "native_control_unqualified")
        return {key: body[key] for key in ("request_id", "target_admission_id", "command")}

    def admit(self, grant, body):
        operation = self.operation(body)
        origin = FamilyAdmission.origin(grant)
        target = body["target_admission_id"] or ""
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                row = self.authority._grant(grant)
                if row["lifecycle"] != "STARTING":
                    raise Fault(403, "native_control_origin_fenced")
                if self.store.db.execute(
                    "SELECT 1 FROM native_control_attempts WHERE request_id=? OR "
                    "(execution_id=? AND target_id=?)",
                    (body["request_id"], grant.execution_id, target),
                ).fetchone():
                    # Neither the same key nor a fresh UUID can replay a RUN.
                    raise Fault(409, "native_control_already_attempted")
                if target:
                    if self.authority.native_children is None:
                        raise Fault(403, "native_control_target_fenced")
                    child = self.store.db.execute(
                        "SELECT * FROM child_admissions WHERE id=?", (target,)
                    ).fetchone()
                    if (
                        child is None
                        or child["execution_id"] != grant.execution_id
                        or child["origin_hash"] != origin
                        or child["state"] != "CONSUMED"
                    ):
                        raise Fault(403, "native_control_target_fenced")
                if (
                    self.store.db.execute(
                        "SELECT COUNT(*) FROM native_control_attempts"
                    ).fetchone()[0]
                    >= 4096
                    or self.store.db.execute(
                        "SELECT COUNT(*) FROM native_control_attempts WHERE execution_id=?",
                        (grant.execution_id,),
                    ).fetchone()[0]
                    >= 65
                ):
                    raise Fault(503, "native_control_capacity")
                self.store.db.execute(
                    "INSERT INTO native_control_attempts VALUES(?,?,?,?,?,?,'DISPATCH_UNCERTAIN',NULL)",
                    (
                        body["request_id"],
                        grant.execution_id,
                        target,
                        origin,
                        digest(operation),
                        body["command"],
                    ),
                )
                self.store._event(
                    "NATIVE_CONTROL_ATTEMPT_ADMITTED",
                    dict(execution_id=grant.execution_id, origin_hash=origin, **operation),
                )
                return dict(
                    admitted=True,
                    execution_id=grant.execution_id,
                    **operation,
                    origin_hash=origin,
                    operation_digest=digest(operation),
                    state="DISPATCH_UNCERTAIN",
                    quiescence_proven=False,
                    effective_transfer=False,
                    hold_retained=True,
                    runtime_enabled=False,
                )

    def forward(self, grant, body):
        """One live admission immediately before native Context forwards RUN.

        This cannot prove Executor dequeue or close the post-admission interval.
        An unknown IPC outcome remains held, never replayed or upgraded to proof.
        """
        operation = self.operation(body)
        origin, hashed = FamilyAdmission.origin(grant), digest(operation)
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                self.authority._grant(grant)
                row = self.store.db.execute(
                    "SELECT * FROM native_control_attempts WHERE request_id=?",
                    (body["request_id"],),
                ).fetchone()
                if (
                    row is None
                    or row["execution_id"] != grant.execution_id
                    or row["origin_hash"] != origin
                    or row["operation_digest"] != hashed
                    or row["state"] != "DISPATCH_UNCERTAIN"
                ):
                    raise Fault(403, "native_control_origin_fenced")
                if self.store.db.execute(
                    "SELECT 1 FROM native_control_forwards WHERE request_id=?",
                    (body["request_id"],),
                ).fetchone():
                    raise Fault(409, "native_control_forward_replay_denied")
                self.store.db.execute(
                    "INSERT INTO native_control_forwards VALUES(?,?,?,?,'FORWARD_UNPROVEN')",
                    (body["request_id"], grant.execution_id, origin, hashed),
                )
                self.store._event(
                    "NATIVE_CONTROL_FORWARD_ADMITTED",
                    dict(execution_id=grant.execution_id, origin_hash=origin, **operation),
                )
                return dict(
                    forward_admitted=True,
                    execution_id=grant.execution_id,
                    **operation,
                    origin_hash=origin,
                    operation_digest=hashed,
                    state="FORWARD_UNPROVEN",
                    quiescence_proven=False,
                    effective_transfer=False,
                    hold_retained=True,
                    runtime_enabled=False,
                )

    def report(self, grant, body):
        operation = self.operation(body)
        outcome = body["outcome"]
        if type(outcome) is not str or outcome not in {"IPC_SEND_ACKNOWLEDGED", "UNCERTAIN"}:
            raise Fault(403, "native_control_outcome_unqualified")
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                # Safety-only diagnostics after a fence cannot admit an effect.
                self.authority._original_grant(grant)
                row = self.store.db.execute(
                    "SELECT * FROM native_control_attempts WHERE request_id=?",
                    (body["request_id"],),
                ).fetchone()
                if (
                    row is None
                    or row["execution_id"] != grant.execution_id
                    or row["origin_hash"] != FamilyAdmission.origin(grant)
                    or row["operation_digest"] != digest(operation)
                    or row["state"] == "RESTART_FENCED"
                ):
                    raise Fault(403, "native_control_origin_fenced")
                if row["outcome"] is not None and row["outcome"] != outcome:
                    raise Fault(409, "native_control_report_conflict")
                if row["outcome"] is None:
                    self.store.db.execute(
                        "UPDATE native_control_attempts SET outcome=? WHERE request_id=?",
                        (outcome, body["request_id"]),
                    )
                    self.store._event(
                        "NATIVE_CONTROL_TRANSPORT_REPORTED",
                        dict(execution_id=grant.execution_id, outcome=outcome, **operation),
                    )
                # Deliberately retain DISPATCH_UNCERTAIN even for IPC ACK.
                return dict(
                    recorded=True,
                    request_id=body["request_id"],
                    execution_id=grant.execution_id,
                    outcome=outcome,
                    state=row["state"],
                    quiescence_proven=False,
                    effective_transfer=False,
                    hold_retained=True,
                    runtime_enabled=False,
                )
