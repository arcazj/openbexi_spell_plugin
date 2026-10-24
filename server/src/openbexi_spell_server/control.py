"""Durable, single-attempt native RUN journal; never queue-settlement proof.

The private retained profile permits one agent RUN per admitted native member.
Commit uncertainty before IPC. Even a send acknowledgment leaves that command
unproven: the frozen mailbox can discard it, and this journal is not a native
settlement proof. Final initial RUN consumption is separately admitted, but
still unresolved after permission. No row authorizes handoff, replay, resume or reservation release.
"""

import json

from .contracts import Fault, digest, fingerprint
from .family import FamilyAdmission
from .preflight import canonical_uuid


class NativeControlJournal:
    def __init__(self, authority, *, catalog=None):
        self.authority, self.store = authority, authority.store
        self.catalog = catalog or getattr(authority.native_children, "catalog", None)
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
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_control_consumptions("
                "request_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,origin_hash TEXT NOT NULL,"
                "operation_digest TEXT NOT NULL,state TEXT NOT NULL)"
            )
            self.store.db.execute("UPDATE native_control_consumptions SET state='RESTART_FENCED'")
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 13:
                self.store.db.execute("PRAGMA user_version=13")
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_members("
                "execution_id TEXT NOT NULL,target_id TEXT NOT NULL,instance_id TEXT NOT NULL,"
                "pid INTEGER NOT NULL,parent_pid INTEGER NOT NULL,start_ticks INTEGER NOT NULL,"
                "executable_sha256 TEXT NOT NULL,origin_hash TEXT NOT NULL,"
                "binding_hash TEXT NOT NULL,state TEXT NOT NULL,"
                "PRIMARY KEY(execution_id,target_id),UNIQUE(execution_id,instance_id),"
                "UNIQUE(execution_id,pid))"
            )
            self.store.db.execute("UPDATE native_members SET state='RESTART_FENCED'")
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 14:
                self.store.db.execute("PRAGMA user_version=14")
        authority.native_controls = self

    def bind_member(self, grant, body):
        """Durable agent-observed identity, never host attestation or pause proof."""
        target = body["target_admission_id"]
        if target is not None:
            canonical_uuid(target)
        for key, maximum in (
            ("pid", 2**31 - 1),
            ("parent_pid", 2**31 - 1),
            ("start_ticks", 2**63 - 1),
        ):
            if type(body[key]) is not int or not 1 <= body[key] <= maximum:
                raise Fault(400, "native_member_identity_invalid")
        if body["pid"] == body["parent_pid"] or type(body["instance_id"]) is not str:
            raise Fault(400, "native_member_identity_invalid")
        fingerprint(body["executable_sha256"])
        fields = {
            key: body[key]
            for key in (
                "target_admission_id",
                "instance_id",
                "pid",
                "parent_pid",
                "start_ticks",
                "executable_sha256",
            )
        }
        origin, hashed = FamilyAdmission.origin(grant), digest(fields)
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                row = self.authority._grant(grant)
                if self.catalog is None or row["lifecycle"] != "STARTING":
                    raise Fault(403, "native_member_origin_fenced")
                if target is None:
                    entry = self.catalog.entries.get(row["procedure_id"])
                    if entry is None:
                        raise Fault(403, "native_member_source_fenced")
                    inventory = json.loads(row["inventory"])
                    if any(
                        entry[key] != inventory[key]
                        for key in (
                            "source_revision",
                            "source_sha256",
                            "runtime_image",
                            "driver_binding",
                        )
                    ):
                        raise Fault(403, "native_member_source_fenced")
                    manifest = json.loads(entry["manifest"])
                    if digest(manifest) != entry["source_sha256"]:
                        raise Fault(403, "native_member_source_fenced")
                    entrypoint = manifest["entrypoint"]
                else:
                    if self.authority.native_children is None:
                        raise Fault(403, "native_member_target_fenced")
                    child = self.store.db.execute(
                        "SELECT * FROM child_admissions WHERE id=?", (target,)
                    ).fetchone()
                    if (
                        child is None
                        or child["execution_id"] != grant.execution_id
                        or child["origin_hash"] != origin
                        or child["state"] != "CONSUMED"
                    ):
                        raise Fault(403, "native_member_target_fenced")
                    entrypoint = child["entrypoint"]
                    if (
                        self.authority.native_children._target(row, entrypoint)
                        != child["procedure_id"]
                    ):
                        raise Fault(403, "native_member_source_fenced")
                    parent = self.store.db.execute(
                        "SELECT parent_pid,executable_sha256 FROM native_members WHERE execution_id=? AND target_id=? AND origin_hash=? AND state='REGISTERED_UNPROVEN'",
                        (grant.execution_id, child["parent_id"] or "", origin),
                    ).fetchone()
                    if (
                        parent is None
                        or parent[0] != body["parent_pid"]
                        or parent[1] != body["executable_sha256"]
                    ):
                        raise Fault(403, "native_member_parent_fenced")
                prefix = entrypoint[:-3] + "#"
                suffix = body["instance_id"][len(prefix) :]
                if (
                    not body["instance_id"].startswith(prefix)
                    or not 1 <= len(suffix) <= 9
                    or not suffix.isascii()
                    or not suffix.isdecimal()
                    or str(int(suffix)) != suffix
                ):
                    raise Fault(400, "native_member_instance_invalid")
                if self.store.db.execute(
                    "SELECT 1 FROM native_members WHERE execution_id=? AND (target_id=? OR instance_id=? OR pid=?)",
                    (grant.execution_id, target or "", body["instance_id"], body["pid"]),
                ).fetchone():
                    raise Fault(409, "native_member_already_attempted")
                if (
                    self.store.db.execute("SELECT COUNT(*) FROM native_members").fetchone()[0]
                    >= 4096
                    or self.store.db.execute(
                        "SELECT COUNT(*) FROM native_members WHERE execution_id=?",
                        (grant.execution_id,),
                    ).fetchone()[0]
                    >= 65
                ):
                    raise Fault(503, "native_member_capacity")
                self.store.db.execute(
                    "INSERT INTO native_members VALUES(?,?,?,?,?,?,?,?,?,'REGISTERED_UNPROVEN')",
                    (
                        grant.execution_id,
                        target or "",
                        body["instance_id"],
                        body["pid"],
                        body["parent_pid"],
                        body["start_ticks"],
                        body["executable_sha256"],
                        origin,
                        hashed,
                    ),
                )
                self.store._event(
                    "NATIVE_MEMBER_REGISTERED",
                    dict(
                        execution_id=grant.execution_id,
                        origin_hash=origin,
                        binding_hash=hashed,
                        target_admission_id=target,
                    ),
                )
                return dict(
                    registered=True,
                    execution_id=grant.execution_id,
                    **fields,
                    origin_hash=origin,
                    binding_hash=hashed,
                    state="REGISTERED_UNPROVEN",
                    host_attested=False,
                    quiescence_proven=False,
                    effective_transfer=False,
                    hold_retained=True,
                    runtime_enabled=False,
                )

    def _member(self, grant, target):
        if (
            self.store.db.execute(
                "SELECT 1 FROM native_members WHERE execution_id=? AND target_id=? AND origin_hash=? AND state='REGISTERED_UNPROVEN'",
                (grant.execution_id, target or "", FamilyAdmission.origin(grant)),
            ).fetchone()
            is None
        ):
            raise Fault(403, "native_member_unregistered")

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
                self._member(grant, body["target_admission_id"])
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

    def consume(self, grant, body):
        """One live admission at the native Executor command-consumption boundary.

        This cannot settle the post-admission execution interval or prove quiescence.
        An unknown IPC outcome remains held, never replayed or upgraded to proof.
        """
        operation = self.operation(body)
        origin, hashed = FamilyAdmission.origin(grant), digest(operation)
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                self.authority._grant(grant)
                self._member(grant, body["target_admission_id"])
                row = self.store.db.execute(
                    "SELECT * FROM native_control_forwards WHERE request_id=?",
                    (body["request_id"],),
                ).fetchone()
                if (
                    row is None
                    or row["execution_id"] != grant.execution_id
                    or row["origin_hash"] != origin
                    or row["operation_digest"] != hashed
                    or row["state"] != "FORWARD_UNPROVEN"
                ):
                    raise Fault(403, "native_control_origin_fenced")
                if self.store.db.execute(
                    "SELECT 1 FROM native_control_consumptions WHERE request_id=?",
                    (body["request_id"],),
                ).fetchone():
                    raise Fault(409, "native_control_consume_replay_denied")
                self.store.db.execute(
                    "INSERT INTO native_control_consumptions VALUES(?,?,?,?,'EXECUTION_UNPROVEN')",
                    (body["request_id"], grant.execution_id, origin, hashed),
                )
                self.store._event(
                    "NATIVE_CONTROL_CONSUMPTION_ADMITTED",
                    dict(execution_id=grant.execution_id, origin_hash=origin, **operation),
                )
                return dict(
                    consume_admitted=True,
                    execution_id=grant.execution_id,
                    **operation,
                    origin_hash=origin,
                    operation_digest=hashed,
                    state="EXECUTION_UNPROVEN",
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
