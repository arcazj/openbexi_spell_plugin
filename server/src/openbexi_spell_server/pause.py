"""Opt-in fenced native pause probe. No provider can yet authorize transfer.

The frozen provider reports only an Executor status. Neither that status nor a
worker-supplied Boolean proves thread/child/control/prompt quiescence. This
coordinator therefore records UNPROVEN/EXPIRED and retains ownership and holds.
"""

from dataclasses import asdict
import json
import uuid

from .contracts import Fault, digest
from .preflight import canonical_uuid


class NativePauseBarrier:
    def __init__(self, authority):
        self.authority, self.store = authority, authority.store
        if getattr(authority, "native_pause", None) is not None:
            raise ValueError("Context already has a native pause coordinator")
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_pause_barriers("
                "execution_id TEXT PRIMARY KEY,barrier_id TEXT UNIQUE NOT NULL,"
                "claim_id TEXT NOT NULL,origin_hash TEXT NOT NULL,"
                "state TEXT NOT NULL,deadline REAL NOT NULL,report_hash TEXT,report TEXT)"
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 9:
                self.store.db.execute("PRAGMA user_version=9")
            self.store.db.execute(
                "UPDATE native_pause_barriers SET state='RESTART_FENCED' WHERE state='REQUESTED'"
            )
            self.store.db.execute("UPDATE claims SET state='INVALIDATED' WHERE state='PAUSING'")
        authority.native_pause = self

    def begin(self, row, claim):
        """Called inside the original accept's execution mutex and transaction."""
        if row["lifecycle"] != "STARTING" or not row["start_binding"]:
            raise Fault(409, "native_pause_origin_unavailable")
        if self.store.db.execute(
            "SELECT 1 FROM native_pause_barriers WHERE execution_id=?", (row["id"],)
        ).fetchone():
            raise Fault(409, "native_pause_already_attempted")
        barrier, deadline = str(uuid.uuid4()), self.authority.clock() + 10
        self.store.db.execute(
            "INSERT INTO native_pause_barriers VALUES(?,?,?,?,'REQUESTED',?,NULL,NULL)",
            (row["id"], barrier, claim["id"], digest(json.loads(row["start_binding"])), deadline),
        )
        # This same mutex serializes the final old-grant check and actual send.
        # No network/provider wait occurs here; unrelated executions are free.
        self.store.db.execute(
            "UPDATE executions SET control_state='PAUSING',cap_hash=NULL WHERE id=?", (row["id"],)
        )
        self.store.db.execute("UPDATE claims SET state='PAUSING' WHERE id=?", (claim["id"],))
        self.store._event(
            "CONTROL_TRANSFER_PAUSE_REQUESTED",
            dict(
                execution_id=row["id"], barrier_id=barrier, claim_id=claim["id"], epoch=row["epoch"]
            ),
        )
        return dict(
            claim_id=claim["id"],
            state="PAUSING",
            barrier_id=barrier,
            deadline=deadline,
            effective_transfer=False,
            hold_retained=True,
        )

    def _finish(self, row, state):
        self.store.db.execute(
            "UPDATE native_pause_barriers SET state=? WHERE execution_id=?",
            (state, row["execution_id"]),
        )
        self.store.db.execute(
            "UPDATE executions SET control_state='RECOVERY_REQUIRED',cap_hash=NULL WHERE id=?",
            (row["execution_id"],),
        )
        self.store.db.execute(
            "UPDATE claims SET state='BLOCKED' WHERE id=? AND state='PAUSING'", (row["claim_id"],)
        )
        self.store._event(
            "CONTROL_TRANSFER_PAUSE_UNPROVEN",
            dict(execution_id=row["execution_id"], barrier_id=row["barrier_id"], state=state),
        )

    def _expire_locked(self):
        # Every affected execution was fenced under its mutex at begin(). This
        # short transaction only tightens the fence; it never admits an effect.
        rows = self.store.db.execute(
            "SELECT * FROM native_pause_barriers WHERE state='REQUESTED' AND deadline<=?",
            (self.authority.clock(),),
        ).fetchall()
        for row in rows:
            self._finish(row, "EXPIRED")

    def expire(self):
        with self.store.transaction():
            self._expire_locked()

    def snapshot(self, execution_id):
        row = self.store.db.execute(
            "SELECT * FROM native_pause_barriers WHERE execution_id=?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(
            barrier_id=row["barrier_id"],
            claim_id=row["claim_id"],
            state=row["state"],
            deadline=row["deadline"],
            report=json.loads(row["report"]) if row["report"] else None,
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=bool(
                self.store.db.execute(
                    "SELECT 1 FROM reservations WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
            ),
        )

    def poll(self, grant):
        with self.store.transaction():
            self._expire_locked()
            execution = self.authority._original_grant(grant)
            row = self.store.db.execute(
                "SELECT * FROM native_pause_barriers WHERE execution_id=?", (grant.execution_id,)
            ).fetchone()
            if row is None:
                return dict(
                    action="none" if execution["control_state"] == "OWNED" else "hold",
                    execution_id=grant.execution_id,
                )
            self._origin(row, grant)
            return dict(
                action="pause" if row["state"] == "REQUESTED" else "hold",
                execution_id=grant.execution_id,
                barrier_id=row["barrier_id"],
                deadline=row["deadline"],
            )

    @staticmethod
    def _origin(row, grant):
        fields = asdict(grant)
        fields.pop("token")
        if row["origin_hash"] != digest(fields):
            raise Fault(403, "native_pause_origin_fenced")

    def report(self, grant, payload):
        canonical_uuid(payload["barrier_id"])
        if (
            any(type(payload[key]) is not str for key in ("provider", "native_status", "reason"))
            or payload["provider"] != "legacy-status-only/1"
            or payload["quiescence_proven"] is not False
            or payload["native_status"]
            not in {
                "RUNNING",
                "PAUSED",
                "WAITING",
                "PROMPT",
                "INTERRUPTED",
                "UNKNOWN",
                "ERROR",
                "FINISHED",
                "ABORTED",
            }
            or payload["reason"]
            not in {
                "thread_child_queue_proof_unavailable",
                "pause_timeout",
                "native_channel_failure",
                "non_running_state_unqualified",
            }
        ):
            raise Fault(403, "native_quiescence_proof_unqualified")
        diagnostic = {
            key: payload[key]
            for key in ("provider", "native_status", "quiescence_proven", "reason")
        }
        hashed = digest(diagnostic)
        with self.authority._execution_lock(grant.execution_id):
            with self.store.transaction():
                self._expire_locked()
                self.authority._original_grant(grant)
                row = self.store.db.execute(
                    "SELECT * FROM native_pause_barriers WHERE execution_id=? AND barrier_id=?",
                    (grant.execution_id, payload["barrier_id"]),
                ).fetchone()
                if row is None:
                    raise Fault(403, "native_pause_origin_fenced")
                self._origin(row, grant)
                if row["report_hash"]:
                    if row["report_hash"] != hashed:
                        raise Fault(409, "native_pause_report_conflict")
                else:
                    self.store.db.execute(
                        "UPDATE native_pause_barriers SET report_hash=?,report=? WHERE execution_id=?",
                        (hashed, json.dumps(diagnostic, sort_keys=True), grant.execution_id),
                    )
                    if row["state"] == "REQUESTED":
                        self._finish(row, "UNPROVEN")
                    self.store._event(
                        "NATIVE_PAUSE_DIAGNOSTIC_RECORDED",
                        dict(
                            execution_id=grant.execution_id,
                            barrier_id=payload["barrier_id"],
                            **diagnostic,
                        ),
                    )
                return self.snapshot(grant.execution_id)
