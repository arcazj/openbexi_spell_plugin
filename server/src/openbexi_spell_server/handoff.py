"""Private host-freezer handoff of an existing, sealed native process family.

The separately pinned deployment host owns Docker/cgroup inspection. Runtime
credentials rotate once per accepted transfer, after explicit family resume.
This profile does not permit new children after the original family is sealed.
"""

from contextlib import nullcontext
from dataclasses import asdict, replace
import hmac
import json
import secrets
import uuid

from .authority import secret_hash
from .contracts import Fault, canonical, digest, exact, fingerprint
from .pause import NativePauseBarrier
from .preflight import canonical_uuid


class LiveFamilyHandoff(NativePauseBarrier):
    SCHEMA = "openbexi.host-handoff/1"
    MAX_TRANSFERS = 8

    def __init__(self, authority):
        if authority.terminal_settlement is None or authority.native_prompts is None:
            raise ValueError("Host handoff requires separate host binding and all native journals")
        super().__init__(authority)
        self.host = authority.terminal_settlement
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS live_handoffs("
                "execution_id TEXT PRIMARY KEY,barrier_id TEXT UNIQUE NOT NULL,"
                "origin_hash TEXT NOT NULL,old_binding TEXT NOT NULL,old_token_hash TEXT NOT NULL,"
                "old_capability_hash TEXT NOT NULL,roster_hash TEXT NOT NULL,"
                "state TEXT NOT NULL,evidence_hash TEXT,resume_id TEXT UNIQUE,new_request_id TEXT)"
            )
            self.store.db.execute("UPDATE live_handoffs SET state='RESTART_FENCED'")
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS live_handoff_history("
                "execution_id TEXT NOT NULL,barrier_id TEXT PRIMARY KEY,"
                "handoff TEXT NOT NULL,pause_barrier TEXT NOT NULL)"
            )
            if "kind" not in {
                row["name"] for row in self.store.db.execute("PRAGMA table_info(live_handoffs)")
            }:
                self.store.db.execute(
                    "ALTER TABLE live_handoffs ADD COLUMN kind TEXT NOT NULL DEFAULT 'transfer'"
                )
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_rebindings("
                "barrier_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,subject TEXT NOT NULL,"
                "old_connection_id TEXT NOT NULL,new_connection_id TEXT NOT NULL,"
                "expected_epoch INTEGER NOT NULL,expected_generation INTEGER NOT NULL,"
                "state TEXT NOT NULL)"
            )
            self.store.db.execute(
                "UPDATE native_rebindings SET state='RESTART_FENCED' WHERE state='REQUESTED'"
            )
            self.store.db.execute("PRAGMA user_version=21")
        authority.live_handoff = self

    def record(self, execution_id):
        return self.store.db.execute(
            "SELECT * FROM live_handoffs WHERE execution_id=?", (execution_id,)
        ).fetchone()

    def _roster_check(self, execution):
        members, children = self.host._roster(execution["id"])
        prior = self.record(execution["id"])
        origin = prior["origin_hash"] if prior else digest(json.loads(execution["start_binding"]))
        expected = {""} | {c["id"] for c in children}
        if (
            not members
            or {m["target_id"] for m in members} != expected
            or any(
                m["state"] != "REGISTERED_UNPROVEN" or m["origin_hash"] != origin for m in members
            )
            or any(
                c["state"] != "CONSUMED"
                or c["origin_hash"] != origin
                or (c["parent_id"] or "") not in expected
                for c in children
            )
        ):
            raise Fault(409, "handoff_family_unresolved")
        return digest(dict(members=members, children=children))

    def begin(self, row, claim, *, rebind=False):
        self.host.require_bound(row)
        if self.authority.native_commands.terminal_pending(row["id"]):
            raise Fault(409, "handoff_terminal_pending")
        roster = self._roster_check(row)
        # A known open prompt is rejected before changing A's authority. A racing
        # prompt is fenced by begin and independently checked before transfer.
        self._prompts_settled(row["id"])
        receipt = self.store.db.execute(
            "SELECT * FROM worker_runtime_receipts WHERE execution_id=?", (row["id"],)
        ).fetchone()
        if receipt is None:
            raise Fault(409, "handoff_runtime_unavailable")
        prior = self.record(row["id"])
        origin = prior["origin_hash"] if prior else digest(json.loads(row["start_binding"]))
        if prior is not None:
            if prior["state"] != "ACTIVE":
                raise Fault(409, "handoff_previous_unresolved")
            if (
                self.store.db.execute(
                    "SELECT COUNT(*) FROM live_handoff_history WHERE execution_id=?", (row["id"],)
                ).fetchone()[0]
                >= self.MAX_TRANSFERS - 1
            ):
                raise Fault(409, "handoff_transfer_capacity_reached")
            self._journals_settled(row)
            barrier = self.store.db.execute(
                "SELECT * FROM native_pause_barriers WHERE execution_id=?", (row["id"],)
            ).fetchone()
            if barrier is None or barrier["state"] != "PROVEN":
                raise Fault(409, "handoff_previous_unresolved")
            # Inside accept's execution mutex and transaction: archive the
            # completed round atomically with fencing the next one. A failed
            # begin rolls this back; historical host proofs are never current.
            self.store.db.execute(
                "INSERT INTO live_handoff_history VALUES(?,?,?,?)",
                (
                    row["id"],
                    prior["barrier_id"],
                    canonical(dict(prior)).decode(),
                    canonical(dict(barrier)).decode(),
                ),
            )
            self.store.db.execute(
                "DELETE FROM native_pause_barriers WHERE execution_id=?", (row["id"],)
            )
            self.store.db.execute("DELETE FROM live_handoffs WHERE execution_id=?", (row["id"],))
        result = super().begin(row, claim, rebind=rebind)
        self.store.db.execute(
            "UPDATE native_pause_barriers SET deadline=? WHERE execution_id=?",
            (self.authority.clock() + 90, row["id"]),
        )
        self.store.db.execute(
            "INSERT INTO live_handoffs VALUES(?,?,?,?,?,?,?,'REQUESTED',NULL,NULL,NULL,?)",
            (
                row["id"],
                result["barrier_id"],
                origin,
                row["start_binding"],
                row["start_hash"],
                receipt["capability_hash"],
                roster,
                "rebind" if rebind else "transfer",
            ),
        )
        return self.snapshot(row["id"])

    def begin_rebind(self, subject, payload, execution):
        """Same owner and epoch; no new authority until a separate host proof."""
        self.authority._require(subject, "execution:control", "execution:start")
        if (
            execution["control_state"] not in {"OWNED", "CONTROLLER_DISCONNECTED"}
            or execution["authority_incarnation"] != self.store.incarnation
            or payload["connection_id"] == execution["connection_id"]
        ):
            raise Fault(409, "native_rebind_unavailable")
        self._journals_settled(execution)
        result = self.begin(execution, dict(id=str(uuid.uuid4())), rebind=True)
        self.store.db.execute(
            "INSERT INTO native_rebindings VALUES(?,?,?,?,?,?,?,'REQUESTED')",
            (
                result["barrier_id"],
                execution["id"],
                subject,
                execution["connection_id"],
                payload["connection_id"],
                execution["epoch"],
                execution["connection_generation"],
            ),
        )
        self.authority._invalidate_claims(execution["id"])
        return dict(
            **self.authority._public(self.authority._execution(execution["id"])),
            rebind_pending=True,
            barrier_id=result["barrier_id"],
            effective_transfer=False,
        )

    def _prompts_settled(self, execution_id):
        if self.store.db.execute(
            "SELECT 1 FROM native_prompts WHERE execution_id=? AND (state!='CLOSED' "
            "OR outcome IS NULL OR outcome NOT IN "
            "('ANSWER_SELECTED','CANCEL_SELECTED','TIMEOUT','TERMINAL_CANCELLED'))",
            (execution_id,),
        ).fetchone():
            raise Fault(409, "handoff_prompt_unresolved")

    def _journals_settled(self, execution):
        eid = execution["id"]
        self._prompts_settled(eid)
        if not self.host._effects(execution)[0]:
            raise Fault(409, "handoff_effects_unresolved")
        if (
            getattr(self.authority, "driver_gate", None) is not None
            and self.store.db.execute(
                "SELECT 1 FROM native_driver_calls WHERE execution_id=? AND state!='COMPLETED'",
                (eid,),
            ).fetchone()
        ):
            raise Fault(409, "handoff_driver_call_unresolved")
        # Only consumed commands could have crossed their final authority gate.
        # Those MUST have returned/discarded before the freezer proof. Earlier
        # queued stages retain their old identity and cannot consume after rotation.
        for table, key, dispositions in (
            ("native_control_consumptions", "request_id", "native_control_dispositions"),
            ("native_owner_commands", "command_id", "native_owner_command_dispositions"),
        ):
            if self.store.db.execute(
                f"SELECT 1 FROM {table} c LEFT JOIN {dispositions} d ON c.{key}=d.{key} "
                "WHERE c.execution_id=? AND c.state='EXECUTION_UNPROVEN' "
                "AND (d.disposition IS NULL OR d.disposition NOT IN ('HANDLER_RETURNED','DISCARDED_PENDING'))",
                (eid,),
            ).fetchone():
                raise Fault(409, "handoff_native_handler_unresolved")

    def _expire_locked(self):
        super()._expire_locked()
        if not hasattr(self, "host"):
            return
        rows = self.store.db.execute(
            "SELECT h.execution_id,h.barrier_id FROM live_handoffs h "
            "JOIN native_pause_barriers p USING(execution_id) "
            "WHERE h.state NOT IN ('ACTIVE','EXPIRED','RESTART_FENCED','TERMINAL_FENCED') AND p.deadline<=?",
            (self.authority.clock(),),
        ).fetchall()
        for row in rows:
            self.store.db.execute(
                "UPDATE live_handoffs SET state='EXPIRED' WHERE execution_id=?", (row[0],)
            )
            self.store.db.execute(
                "UPDATE native_pause_barriers SET state='EXPIRED' WHERE execution_id=?", (row[0],)
            )
            self.store.db.execute(
                "UPDATE executions SET control_state='RECOVERY_REQUIRED',cap_hash=NULL WHERE id=?",
                (row[0],),
            )
            self.store.db.execute(
                "UPDATE claims SET state='BLOCKED' WHERE execution_id=? AND state='PAUSING'",
                (row[0],),
            )
            self.store.db.execute(
                "UPDATE native_rebindings SET state='EXPIRED' WHERE barrier_id=? AND state='REQUESTED'",
                (row[1],),
            )
            self.store._event("LIVE_HANDOFF_EXPIRED", dict(execution_id=row[0], barrier_id=row[1]))

    def snapshot(self, execution_id):
        result = super().snapshot(execution_id)
        row = self.record(execution_id)
        if result is None or row is None:
            return result
        result.update(
            state=row["state"],
            quiescence_proven=row["state"] in {"TRANSFERRED_PAUSED", "RESUME_REQUESTED"},
            effective_transfer=row["kind"] == "transfer"
            and row["state"]
            in {"TRANSFERRED_PAUSED", "RESUME_REQUESTED", "RESUME_AUTHORIZED", "ACTIVE"},
            operation=row["kind"],
            connection_rebound=row["kind"] == "rebind"
            and row["state"]
            in {"TRANSFERRED_PAUSED", "RESUME_REQUESTED", "RESUME_AUTHORIZED", "ACTIVE"},
            family_roster_sealed=True,
            runtime_identity_rotated=row["state"] == "ACTIVE",
        )
        if row["kind"] == "rebind":
            result["rebind_request_id"] = result.pop("claim_id")
        return result

    def poll(self, grant):
        with self.store.transaction():
            self._expire_locked()
            self.authority._original_grant(grant)
            row = self.record(grant.execution_id)
            return dict(
                action="host_pause"
                if row and row["state"] == "REQUESTED"
                else "hold"
                if row
                else "none",
                execution_id=grant.execution_id,
            )

    def report(self, grant, payload):
        raise Fault(403, "host_freezer_proof_required")

    def _evidence(self, execution, row, evidence):
        exact(
            evidence,
            {
                "provider",
                "container_id",
                "image",
                "paused",
                "running",
                "frozen",
                "oom_killed",
                "restart_count",
                "original_handles",
                "alive_handles",
                "member_bindings",
                "roster_hash",
            },
        )
        binding = self.host._record(execution["id"])
        members, children = self.host._roster(execution["id"])
        if (
            evidence["provider"] != "docker-cgroup-freezer-pidfd/1"
            or binding["state"] != "BOUND"
            or evidence["container_id"] != binding["container_id"]
            or evidence["image"] != binding["image"]
            or any(evidence[k] is not True for k in ("paused", "running", "frozen"))
            or evidence["oom_killed"] is not False
            or type(evidence["restart_count"]) is not int
            or evidence["restart_count"] != 0
            or type(evidence["original_handles"]) is not int
            or not len(members) + 2 <= evidence["original_handles"] <= 512
            or type(evidence["alive_handles"]) is not int
            or evidence["alive_handles"] != evidence["original_handles"]
            or evidence["roster_hash"] != row["roster_hash"]
            or digest(dict(members=members, children=children)) != row["roster_hash"]
            or evidence["member_bindings"] != sorted(m["binding_hash"] for m in members)
        ):
            raise Fault(403, "handoff_host_evidence_invalid")

    def handle(self, peer, path, body):
        if peer != self.host.peer:
            raise Fault(403, "handoff_host_required")
        actions = {
            "status": set(),
            "complete": {"barrier_id", "evidence"},
            "resume": {"barrier_id", "resume_id", "evidence"},
        }
        action = path.removeprefix("/v1/host/handoff/")
        if action not in actions:
            raise Fault(404, "route_not_available")
        exact(
            body,
            {"schema", "context_id", "execution_id", "authority_incarnation"} | actions[action],
        )
        canonical_uuid(body["execution_id"])
        if (
            body["schema"] != self.SCHEMA
            or body["context_id"] != self.store.context_id
            or body["authority_incarnation"] != self.store.incarnation
        ):
            raise Fault(403, "handoff_scope_fenced")
        self.expire()  # Expiry must commit even when the subsequent request fails.
        gate = getattr(self.authority, "driver_gate", None)
        with gate.lock if gate is not None else nullcontext():
            with self.authority._execution_lock(body["execution_id"]):
                with self.store.transaction():
                    execution = self.authority._execution(body["execution_id"])
                    row = self.record(execution["id"])
                    if (
                        row is None
                        or row["state"] in {"EXPIRED", "RESTART_FENCED"}
                        or execution["lifecycle"] != "STARTING"
                    ):
                        raise Fault(403, "handoff_fenced")
                    if action == "status":
                        members, _ = self.host._roster(execution["id"])
                        return dict(
                            **self.snapshot(execution["id"]),
                            members=members,
                            roster_hash=row["roster_hash"],
                            resume_id=row["resume_id"],
                        )
                    if body["barrier_id"] != row["barrier_id"]:
                        raise Fault(403, "handoff_barrier_fenced")
                    self._evidence(execution, row, body["evidence"])
                    if action == "complete":
                        return self._complete(execution, row, body["evidence"])
                    if body["resume_id"] != row["resume_id"] or row["state"] not in {
                        "RESUME_REQUESTED",
                        "RESUME_AUTHORIZED",
                    }:
                        raise Fault(403, "handoff_resume_fenced")
                    self.authority._session(execution["owner"], execution["connection_id"])
                    self.authority._require(
                        execution["owner"], "execution:control", "execution:start"
                    )
                    if not execution["cap_hash"]:
                        raise Fault(403, "handoff_resume_fenced")
                    if row["state"] == "RESUME_REQUESTED":
                        self.store.db.execute(
                            "UPDATE live_handoffs SET state='RESUME_AUTHORIZED' WHERE execution_id=?",
                            (execution["id"],),
                        )
                        self.store._event(
                            "LIVE_FAMILY_RESUME_AUTHORIZED",
                            dict(execution_id=execution["id"], epoch=execution["epoch"]),
                        )
                    return dict(**self.snapshot(execution["id"]), runtime_epoch=row["resume_id"])

    def _complete(self, execution, row, evidence):
        hashed = digest(evidence)
        if row["evidence_hash"]:
            if row["evidence_hash"] != hashed:
                raise Fault(409, "handoff_evidence_conflict")
            return self.snapshot(execution["id"])
        if row["state"] != "REQUESTED" or execution["control_state"] != "PAUSING":
            raise Fault(403, "handoff_not_pausing")
        self._journals_settled(execution)
        if row["kind"] == "rebind":
            self._complete_rebind(execution, row)
        else:
            self._complete_transfer(execution, row)
        self.store.db.execute(
            "UPDATE live_handoffs SET state='TRANSFERRED_PAUSED',evidence_hash=? WHERE execution_id=?",
            (hashed, execution["id"]),
        )
        self.store.db.execute(
            "UPDATE native_pause_barriers SET state='PROVEN' WHERE execution_id=?",
            (execution["id"],),
        )
        return self.snapshot(execution["id"])

    def _complete_rebind(self, execution, row):
        request = self.store.db.execute(
            "SELECT * FROM native_rebindings WHERE barrier_id=?", (row["barrier_id"],)
        ).fetchone()
        if (
            request is None
            or request["state"] != "REQUESTED"
            or request["execution_id"] != execution["id"]
            or request["subject"] != execution["owner"]
            or request["expected_epoch"] != execution["epoch"]
            or request["expected_generation"] != execution["connection_generation"]
            or request["old_connection_id"] != execution["connection_id"]
        ):
            raise Fault(403, "native_rebind_fenced")
        self.authority._session(request["subject"], request["new_connection_id"])
        self.authority._require(request["subject"], "execution:control", "execution:start")
        self.store.db.execute(
            "UPDATE executions SET connection_id=?,connection_generation=connection_generation+1,"
            "cap_hash=NULL,control_state='HANDOFF_PAUSED' WHERE id=?",
            (request["new_connection_id"], execution["id"]),
        )
        self.store.db.execute(
            "UPDATE native_rebindings SET state='REBOUND' WHERE barrier_id=?", (row["barrier_id"],)
        )
        self.store._event(
            "NATIVE_CONTROLLER_REBOUND",
            dict(
                execution_id=execution["id"],
                subject=execution["owner"],
                epoch=execution["epoch"],
                connection_generation=execution["connection_generation"] + 1,
                barrier_id=row["barrier_id"],
            ),
        )

    def _complete_transfer(self, execution, row):
        barrier = self.store.db.execute(
            "SELECT * FROM native_pause_barriers WHERE execution_id=?", (execution["id"],)
        ).fetchone()
        claim = self.store.db.execute(
            "SELECT * FROM claims WHERE id=?", (barrier["claim_id"],)
        ).fetchone()
        if (
            claim is None
            or claim["state"] != "PAUSING"
            or claim["expected_epoch"] != execution["epoch"]
            or claim["expected_owner"] != execution["owner"]
        ):
            raise Fault(403, "handoff_claim_fenced")
        self.authority._session(claim["requester"], claim["connection_id"])
        self.authority._require(
            claim["requester"], "execution:request_control", "execution:control", "execution:start"
        )
        self.store.db.execute(
            "UPDATE executions SET owner=?,epoch=epoch+1,connection_id=?,connection_generation=connection_generation+1,cap_hash=NULL,control_state='HANDOFF_PAUSED' WHERE id=?",
            (claim["requester"], claim["connection_id"], execution["id"]),
        )
        self.store.db.execute("UPDATE claims SET state='ACCEPTED' WHERE id=?", (claim["id"],))
        self.store._event(
            "CONTROL_OWNER_CHANGED",
            dict(
                execution_id=execution["id"],
                owner=claim["requester"],
                epoch=execution["epoch"] + 1,
                barrier_id=row["barrier_id"],
            ),
        )

    def rebind(self, subject, payload, execution):
        row = self.record(execution["id"])
        if (
            row is None
            or row["state"] != "TRANSFERRED_PAUSED"
            or execution["control_state"] != "HANDOFF_PAUSED"
            or payload["connection_id"] != execution["connection_id"]
        ):
            raise Fault(403, "handoff_rebind_fenced")
        capability = secrets.token_hex(32)
        self.store.db.execute(
            "UPDATE executions SET cap_hash=? WHERE id=?",
            (secret_hash(capability), execution["id"]),
        )
        self.store._event(
            "HANDOFF_CONTROLLER_BOUND",
            dict(execution_id=execution["id"], subject=subject, epoch=execution["epoch"]),
        )
        return dict(
            **self.authority._public(execution),
            connection_id=execution["connection_id"],
            capability=capability,
        )

    def request_resume(self, subject, key, payload):
        with self.authority._execution_lock(payload["execution_id"]):
            with self.store.transaction():
                execution = self.authority._execution(payload["execution_id"])
                if execution["control_state"] != "HANDOFF_PAUSED":
                    return None
                self.authority._require(subject, "execution:control", "execution:start")
                self.authority._session(subject, payload["connection_id"])
                if (
                    subject != execution["owner"]
                    or payload["expected_epoch"] != execution["epoch"]
                    or payload["connection_id"] != execution["connection_id"]
                    or payload["connection_generation"] != execution["connection_generation"]
                    or not execution["cap_hash"]
                    or not hmac.compare_digest(
                        secret_hash(payload["capability"]), execution["cap_hash"]
                    )
                ):
                    raise Fault(403, "controller_fenced")
                if payload["command"] != "CMD_RUN" or payload["target_admission_id"] is not None:
                    raise Fault(409, "family_resume_required")
                replay = self.authority._replay(subject, "execution.command", key, payload)
                if replay is not None:
                    return replay
                row = self.record(execution["id"])
                if row is None or row["state"] != "TRANSFERRED_PAUSED":
                    raise Fault(409, "handoff_resume_already_attempted")
                resume_id = str(uuid.uuid4())
                self.store.db.execute(
                    "UPDATE live_handoffs SET state='RESUME_REQUESTED',resume_id=? WHERE execution_id=?",
                    (resume_id, execution["id"]),
                )
                self.store._event(
                    "LIVE_FAMILY_RESUME_REQUESTED",
                    dict(execution_id=execution["id"], subject=subject, epoch=execution["epoch"]),
                )
                return self.authority._record(
                    subject,
                    "execution.command",
                    key,
                    payload,
                    dict(
                        command_id=resume_id,
                        state="RESUME_REQUESTED",
                        family_resume=True,
                        barrier_id=row["barrier_id"],
                    ),
                )

    def activate(self, peer, body):
        """One delivery using the old consumed-worker proof, never a replay route."""
        from .launch import start_grant

        exact(body, {"schema", "context_id", "grant", "runtime_capability", "runtime_epoch"})
        if body["schema"] != "openbexi.worker/2" or body["context_id"] != self.store.context_id:
            raise Fault(403, "handoff_scope_fenced")
        old = start_grant(body["grant"])
        fingerprint(body["runtime_capability"])
        canonical_uuid(body["runtime_epoch"])
        self.expire()
        with self.authority._execution_lock(old.execution_id):
            with self.store.transaction():
                row = self.record(old.execution_id)
                execution = self.authority._execution(old.execution_id)
                fields = asdict(old)
                token = fields.pop("token")
                if (
                    row is None
                    or row["state"] != "RESUME_AUTHORIZED"
                    or row["resume_id"] != body["runtime_epoch"]
                    or row["old_binding"] != canonical(fields).decode()
                    or not hmac.compare_digest(row["old_token_hash"], secret_hash(token))
                    or not hmac.compare_digest(
                        row["old_capability_hash"], secret_hash(body["runtime_capability"])
                    )
                    or old.worker_slot != peer.slot
                    or old.worker_incarnation != peer.incarnation
                    or old.authority_incarnation != self.store.incarnation
                    or execution["control_state"] != "HANDOFF_PAUSED"
                ):
                    raise Fault(403, "handoff_activation_fenced")
                self.authority._session(execution["owner"], execution["connection_id"])
                self.authority._require(execution["owner"], "execution:control", "execution:start")
                if not execution["cap_hash"]:
                    raise Fault(403, "handoff_activation_fenced")
                grant = replace(
                    old,
                    control_epoch=execution["epoch"],
                    connection_id=execution["connection_id"],
                    connection_generation=execution["connection_generation"],
                    request_id=str(uuid.uuid4()),
                    token=secrets.token_hex(32),
                )
                fields = asdict(grant)
                fields.pop("token")
                capability = secrets.token_hex(32)
                self.store.db.execute(
                    "UPDATE executions SET start_hash=?,start_binding=?,control_state='OWNED' WHERE id=?",
                    (secret_hash(grant.token), canonical(fields).decode(), old.execution_id),
                )
                self.store.db.execute(
                    "UPDATE worker_runtime_receipts SET request_id=?,capability_hash=? WHERE execution_id=?",
                    (grant.request_id, secret_hash(capability), old.execution_id),
                )
                self.store.db.execute(
                    "UPDATE live_handoffs SET state='ACTIVE',new_request_id=? WHERE execution_id=?",
                    (grant.request_id, old.execution_id),
                )
                self.store._event(
                    "LIVE_RUNTIME_IDENTITY_ROTATED",
                    dict(
                        execution_id=old.execution_id,
                        epoch=execution["epoch"],
                        request_id=grant.request_id,
                    ),
                )
                return dict(
                    grant=asdict(grant),
                    runtime_capability=capability,
                    runtime_epoch=row["resume_id"],
                    origin_hash=row["origin_hash"],
                    activation_kind=row["kind"],
                )
