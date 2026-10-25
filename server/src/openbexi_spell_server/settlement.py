"""Private single-host terminal settlement, authenticated independently of workers.

The configured host is a trusted deployment principal. It pins the actual Docker
container before start and verifies its original process handles and stopped
container after fencing. Worker reports and browser identities cannot reach this
interface. This terminal proof cannot authorize a live-family controller transfer.
"""

from contextlib import nullcontext
from dataclasses import dataclass
import json
import uuid

from .contracts import Fault, canonical, digest, exact, fingerprint
from .effects import STAGES
from .preflight import canonical_uuid


@dataclass(frozen=True)
class SettlementHost:
    fingerprint: str


class TerminalSettlement:
    SCHEMA = "openbexi.host-terminal/1"
    TERMINAL = frozenset({"FINISHED", "ERROR", "ABORTED", "CLOSED", "UNKNOWN"})

    def __init__(self, authority, config, *, excluded_pins):
        exact(config, {"profile", "fingerprint"})
        if config["profile"] != "single-host-terminal-candidate":
            raise ValueError("Unsupported host settlement profile")
        pin = fingerprint(config["fingerprint"])
        if pin in excluded_pins:
            raise ValueError("Settlement host identity must be separate from worker and Listener")
        if authority.native_controls is None or authority.native_children is None:
            raise ValueError("Terminal settlement requires the native family journals")
        if getattr(authority, "terminal_settlement", None) is not None:
            raise ValueError("Context already has terminal settlement")
        self.authority, self.store, self.peer = authority, authority.store, SettlementHost(pin)
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS terminal_settlements("
                "execution_id TEXT PRIMARY KEY,incarnation TEXT NOT NULL,host TEXT NOT NULL,"
                "container_id TEXT UNIQUE NOT NULL,image TEXT NOT NULL,state TEXT NOT NULL,"
                "challenge TEXT UNIQUE,roster_hash TEXT,native_status TEXT,"
                "report_hash TEXT,report TEXT)"
            )
            self.store.db.execute(
                "UPDATE terminal_settlements SET state='RESTART_FENCED' WHERE state!='RELEASED'"
            )
            self.store.db.execute("PRAGMA user_version=18")
        authority.terminal_settlement = self

    def _record(self, execution_id):
        row = self.store.db.execute(
            "SELECT * FROM terminal_settlements WHERE execution_id=?", (execution_id,)
        ).fetchone()
        if row is None or row["host"] != self.peer.fingerprint:
            raise Fault(403, "terminal_container_unbound")
        if row["incarnation"] != self.store.incarnation or row["state"] == "RESTART_FENCED":
            raise Fault(403, "terminal_settlement_restart_fenced")
        return row

    def _roster(self, execution_id):
        members = [
            dict(row)
            for row in self.store.db.execute(
                "SELECT * FROM native_members WHERE execution_id=? ORDER BY target_id",
                (execution_id,),
            )
        ]
        children = [
            dict(row)
            for row in self.store.db.execute(
                "SELECT id,parent_id,procedure_id,state,origin_hash FROM child_admissions "
                "WHERE execution_id=? ORDER BY id",
                (execution_id,),
            )
        ]
        return members, children

    def handle(self, peer, path, body):
        if peer != self.peer:
            raise Fault(403, "settlement_host_required")
        fields = {"schema", "context_id", "execution_id", "authority_incarnation"}
        actions = {
            "/v1/host/terminal/bind": {"container_id", "image"},
            "/v1/host/terminal/begin": {"container_id", "native_status"},
            "/v1/host/terminal/complete": {"challenge", "evidence"},
            "/v1/host/terminal/release": {"challenge", "report_hash"},
        }
        if path not in actions:
            raise Fault(404, "route_not_available")
        exact(body, fields | actions[path])
        canonical_uuid(body["execution_id"])
        if (
            body["schema"] != self.SCHEMA
            or body["context_id"] != self.store.context_id
            or body["authority_incarnation"] != self.store.incarnation
        ):
            raise Fault(403, "settlement_scope_fenced")
        # Driver ledger -> execution mutex -> Context transaction is the same
        # order as final driver writes. No Docker/network wait occurs here.
        gate = getattr(self.authority, "driver_gate", None)
        with gate.lock if gate is not None else nullcontext():
            with self.authority._execution_lock(body["execution_id"]):
                with self.store.transaction():
                    execution = self.authority._execution(body["execution_id"])
                    if execution["authority_incarnation"] != self.store.incarnation:
                        raise Fault(403, "settlement_scope_fenced")
                    action = path.rsplit("/", 1)[1]
                    return getattr(self, "_" + action)(execution, body)

    def _bind(self, execution, body):
        fingerprint(body["container_id"])
        image = body["image"]
        if type(image) is not str or not image.startswith("sha256:"):
            raise Fault(400, "invalid_terminal_image")
        fingerprint(image[7:])
        if (
            execution["lifecycle"] != "RESERVED"
            or image != json.loads(execution["inventory"])["runtime_image"]
        ):
            raise Fault(403, "terminal_binding_fenced")
        prior = self.store.db.execute(
            "SELECT * FROM terminal_settlements WHERE execution_id=?", (execution["id"],)
        ).fetchone()
        if prior:
            row = self._record(execution["id"])
            if (row["container_id"], row["image"], row["state"]) != (
                body["container_id"],
                image,
                "BOUND",
            ):
                raise Fault(409, "terminal_binding_conflict")
        else:
            if self.store.db.execute(
                "SELECT 1 FROM terminal_settlements WHERE container_id=?", (body["container_id"],)
            ).fetchone():
                raise Fault(409, "terminal_container_already_bound")
            self.store.db.execute(
                "INSERT INTO terminal_settlements VALUES(?,?,?,?,?,'BOUND',NULL,NULL,NULL,NULL,NULL)",
                (
                    execution["id"],
                    self.store.incarnation,
                    self.peer.fingerprint,
                    body["container_id"],
                    image,
                ),
            )
            self.store._event(
                "TERMINAL_HOST_CONTAINER_BOUND",
                dict(
                    execution_id=execution["id"],
                    container_id=body["container_id"],
                    image=image,
                ),
            )
        return dict(state="BOUND", execution_id=execution["id"], container_id=body["container_id"])

    def require_bound(self, execution):
        row = self._record(execution["id"])
        if row["state"] != "BOUND":
            raise Fault(403, "terminal_binding_fenced")

    def _begin(self, execution, body):
        row = self._record(execution["id"])
        if type(body["native_status"]) is not str or body["native_status"] not in self.TERMINAL:
            raise Fault(400, "invalid_terminal_status")
        if row["container_id"] != body["container_id"]:
            raise Fault(403, "terminal_container_fenced")
        if row["state"] != "BOUND":
            if row["native_status"] != body["native_status"]:
                raise Fault(409, "terminal_status_conflict")
            return self.snapshot(execution["id"])
        if execution["lifecycle"] != "STARTING":
            raise Fault(403, "terminal_execution_not_started")
        members, children = self._roster(execution["id"])
        roster_hash = digest(dict(members=members, children=children))
        challenge = str(uuid.uuid4())
        self.store.db.execute(
            "UPDATE terminal_settlements SET state='FENCED',challenge=?,roster_hash=?,native_status=? "
            "WHERE execution_id=?",
            (challenge, roster_hash, body["native_status"], execution["id"]),
        )
        self.store.db.execute(
            "UPDATE executions SET control_state='TERMINATING',cap_hash=NULL WHERE id=?",
            (execution["id"],),
        )
        self.authority._invalidate_claims(execution["id"])
        if self.authority.native_pause is not None:
            self.store.db.execute(
                "UPDATE native_pause_barriers SET state='TERMINAL_FENCED' "
                "WHERE execution_id=? AND state='REQUESTED'",
                (execution["id"],),
            )
        self.store.db.execute(
            "UPDATE claims SET state='INVALIDATED' WHERE execution_id=? AND state='PAUSING'",
            (execution["id"],),
        )
        self.store._event(
            "TERMINAL_SETTLEMENT_FENCED",
            dict(
                execution_id=execution["id"],
                challenge=challenge,
                roster_hash=roster_hash,
            ),
        )
        return self.snapshot(execution["id"])

    def _effects(self, execution):
        gate = getattr(self.authority, "driver_gate", None)
        if gate is None:
            return (json.loads(execution["inventory"])["driver_binding"] == "context-audit", 0)
        if gate.failed or gate.db is None:
            return False, 0
        sql = "SELECT * FROM effect_intents WHERE execution_id=? ORDER BY operation,stage"
        context = [tuple(row) for row in self.store.db.execute(sql, (execution["id"],))]
        driver = [tuple(row) for row in gate.db.execute(sql, (execution["id"],))]
        if context != driver:
            return False, len(context)
        operations: dict[str, tuple[set[str], str]] = {}
        for operation, stage, _execution, provenance, _packet, state, receipt in context:
            if state != "ACKED" or not receipt:
                return False, len(context)
            fingerprint(receipt)
            stages, origin = operations.setdefault(operation, (set(), provenance))
            if origin != provenance:
                return False, len(context)
            stages.add(stage)
        return all(stages == STAGES for stages, _origin in operations.values()), len(context)

    def _complete(self, execution, body):
        row = self._record(execution["id"])
        canonical_uuid(body["challenge"])
        if body["challenge"] != row["challenge"]:
            raise Fault(403, "terminal_challenge_fenced")
        evidence = body["evidence"]
        exact(
            evidence,
            {
                "provider",
                "container_id",
                "image",
                "running",
                "pid",
                "exit_code",
                "oom_killed",
                "restart_count",
                "original_handles",
                "exited_handles",
                "roster_hash",
            },
        )
        if (
            evidence["provider"] != "docker-pidfd-terminal/1"
            or evidence["container_id"] != row["container_id"]
            or evidence["image"] != row["image"]
            or evidence["roster_hash"] != row["roster_hash"]
            or evidence["running"] is not False
            or evidence["oom_killed"] is not False
            or any(
                type(evidence[k]) is not int or evidence[k] != 0
                for k in ("pid", "exit_code", "restart_count")
            )
            or type(evidence["original_handles"]) is not int
            or not 1 <= evidence["original_handles"] <= 512
            or type(evidence["exited_handles"]) is not int
            or evidence["exited_handles"] != evidence["original_handles"]
        ):
            raise Fault(403, "terminal_host_evidence_invalid")
        hashed = digest(evidence)
        if row["report_hash"]:
            if row["report_hash"] != hashed:
                raise Fault(409, "terminal_report_conflict")
            return self.snapshot(execution["id"])
        if row["state"] != "FENCED" or execution["control_state"] != "TERMINATING":
            raise Fault(403, "terminal_settlement_not_fenced")
        members, children = self._roster(execution["id"])
        reasons = []
        if row["native_status"] == "UNKNOWN":
            reasons.append("native_outcome_unknown")
        if digest(dict(members=members, children=children)) != row["roster_hash"]:
            reasons.append("family_roster_changed")
        expected = {""} | {c["id"] for c in children if c["state"] == "CONSUMED"}
        if (
            {m["target_id"] for m in members} != expected
            or any(m["state"] != "REGISTERED_UNPROVEN" for m in members)
            or any(c["state"] not in {"ADMITTED", "CONSUMED"} for c in children)
        ):
            reasons.append("family_membership_unresolved")
        if self.authority.native_prompts is None:
            reasons.append("prompt_journal_unavailable")
        elif self.store.db.execute(
            "SELECT 1 FROM native_prompts WHERE execution_id=? AND state!='CLOSED'",
            (execution["id"],),
        ).fetchone():
            reasons.append("prompt_outcome_unresolved")
        effects_settled, effect_rows = self._effects(execution)
        if not effects_settled:
            reasons.append("external_effects_unresolved")
        report = dict(
            host_evidence=evidence,
            native_status=row["native_status"],
            reasons=reasons,
            native_members=len(members),
            children=len(children),
            effect_receipts=effect_rows,
            process_family_terminated=True,
            pending_native_work_retired=True,
            effects_settled=effects_settled,
            reservation_release_eligible=not reasons,
        )
        state = "HELD" if reasons else "SETTLED"
        self.store.db.execute(
            "UPDATE terminal_settlements SET state=?,report_hash=?,report=? WHERE execution_id=?",
            (state, hashed, canonical(report).decode(), execution["id"]),
        )
        self.store.db.execute(
            "UPDATE executions SET lifecycle=?,control_state=? WHERE id=?",
            (
                "TERMINAL_HELD" if reasons else "TERMINAL_SETTLED",
                "RECOVERY_REQUIRED" if reasons else "TERMINATED",
                execution["id"],
            ),
        )
        self.store._event(
            "TERMINAL_FAMILY_RECONCILED",
            dict(
                execution_id=execution["id"],
                state=state,
                report_hash=hashed,
                reasons=reasons,
            ),
        )
        return self.snapshot(execution["id"])

    def _release(self, execution, body):
        row = self._record(execution["id"])
        if body["challenge"] != row["challenge"] or body["report_hash"] != row["report_hash"]:
            raise Fault(403, "terminal_release_binding_fenced")
        if row["state"] == "RELEASED":
            return self.snapshot(execution["id"])
        if row["state"] != "SETTLED" or execution["lifecycle"] != "TERMINAL_SETTLED":
            raise Fault(409, "terminal_release_unproven")
        released = self.store.db.execute(
            "DELETE FROM reservations WHERE execution_id=?", (execution["id"],)
        ).rowcount
        self.store.db.execute(
            "UPDATE terminal_settlements SET state='RELEASED' WHERE execution_id=?",
            (execution["id"],),
        )
        # Original runtime credentials are destroyed. Never recycle a spent worker.
        self.store.db.execute(
            "UPDATE executions SET epoch=epoch+1,connection_generation=connection_generation+1,"
            "start_hash=NULL,start_binding=NULL,cap_hash=NULL WHERE id=?",
            (execution["id"],),
        )
        self.store._event(
            "TERMINAL_RESERVATIONS_RELEASED",
            dict(
                execution_id=execution["id"],
                report_hash=row["report_hash"],
                released=released,
            ),
        )
        return self.snapshot(execution["id"])

    def snapshot(self, execution_id):
        row = self.store.db.execute(
            "SELECT * FROM terminal_settlements WHERE execution_id=?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(
            execution_id=execution_id,
            state=row["state"],
            challenge=row["challenge"],
            roster_hash=row["roster_hash"],
            report_hash=row["report_hash"],
            report=json.loads(row["report"]) if row["report"] else None,
            hold_retained=row["state"] != "RELEASED",
            worker_reusable=False,
            effective_transfer=False,
            runtime_enabled=False,
        )
