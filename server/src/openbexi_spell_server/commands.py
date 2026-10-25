"""Fresh owner-admitted native commands, separate from startup authority.

This opt-in queue permits fresh RUN, STEP and single-member PAUSE. Delivery,
forwarding and consumption remain unproven outcomes, never family quiescence or
handoff permission. Every physical dispatch is single-attempt.
"""

from dataclasses import asdict, dataclass, fields
import hmac
import math
import secrets
import uuid

from .authority import secret_hash
from .contracts import (
    Fault,
    OWNER_COMMANDS,
    TERMINAL_COMMANDS,
    canonical,
    digest,
    exact,
    fingerprint,
    identifier,
    validate_owner_command_payload,
)
from .family import FamilyAdmission
from .preflight import canonical_uuid


@dataclass(frozen=True)
class OwnerCommandGrant:
    schema: str
    authority_incarnation: str
    execution_id: str
    worker_slot: str
    worker_incarnation: str
    worker_generation: int
    runtime_origin_hash: str
    member_binding_hash: str
    owner: str
    control_epoch: int
    connection_id: str
    connection_generation: int
    command_id: str
    target_admission_id: str | None
    command: str
    operation_digest: str
    expires_at: float
    token: str


def owner_command_grant(value, *, allow_terminal=False):
    exact(value, {field.name for field in fields(OwnerCommandGrant)})
    if (
        value["schema"] != "openbexi.owner-command/1"
        or type(value["command"]) is not str
        or value["command"]
        not in (OWNER_COMMANDS | TERMINAL_COMMANDS if allow_terminal else OWNER_COMMANDS)
    ):
        raise Fault(403, "owner_command_unqualified")
    for key in ("authority_incarnation", "execution_id", "connection_id", "command_id"):
        canonical_uuid(value[key])
    if value["target_admission_id"] is not None:
        canonical_uuid(value["target_admission_id"])
    for key in ("worker_slot", "worker_incarnation", "owner"):
        identifier(value[key])
    for key in ("worker_generation", "control_epoch", "connection_generation"):
        if type(value[key]) is not int or not 1 <= value[key] < 2**63 - 1:
            raise Fault(400, "owner_command_generation_invalid")
    for key in ("runtime_origin_hash", "member_binding_hash", "operation_digest", "token"):
        fingerprint(value[key])
    if (
        type(value["expires_at"]) is not float
        or not math.isfinite(value["expires_at"])
        or not 0 < value["expires_at"] < 10**12
    ):
        raise Fault(400, "owner_command_deadline_invalid")
    return OwnerCommandGrant(**value)


class NativeOwnerCommands:
    def __init__(self, authority, *, terminal=False):
        if type(terminal) is not bool:
            raise ValueError("Explicit terminal profile required")
        self.terminal = terminal
        self.authority, self.store = authority, authority.store
        if authority.native_controls is None or authority.native_commands is not None:
            raise ValueError("Owner commands require one native control/member coordinator")
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_owner_commands("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT,command_id TEXT UNIQUE NOT NULL,"
                "execution_id TEXT NOT NULL,target_id TEXT NOT NULL,owner TEXT NOT NULL,"
                "epoch INTEGER NOT NULL,connection_id TEXT NOT NULL,connection_generation INTEGER NOT NULL,"
                "controller_hash TEXT NOT NULL,runtime_origin_hash TEXT NOT NULL,member_hash TEXT NOT NULL,"
                "command TEXT NOT NULL,operation_digest TEXT NOT NULL,expires_at REAL NOT NULL,"
                "state TEXT NOT NULL,grant_hash TEXT,grant_binding TEXT,diagnostic TEXT)"
            )
            self.store.db.execute("UPDATE native_owner_commands SET state='RESTART_FENCED'")
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 15:
                self.store.db.execute("PRAGMA user_version=15")
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_owner_command_dispositions("
                "command_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,"
                "disposition TEXT NOT NULL)"
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 16:
                self.store.db.execute("PRAGMA user_version=16")
            # A retained terminal intent also fences subsequent driver writes and
            # child/initial-RUN admission. Restart NEVER removes it or restores a token.
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_terminal_intents("
                "command_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, target_id TEXT NOT NULL,"
                "command TEXT NOT NULL,native_status TEXT NOT NULL,prompt_id TEXT,"
                "UNIQUE(execution_id,target_id,command))"
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 18:
                self.store.db.execute("PRAGMA user_version=18")
        authority.native_commands = self

    def _permissions(self, owner, command):
        permissions = (
            ("execution:control", "execution:start")
            if command in {"CMD_RUN", "CMD_STEP"}
            else ("execution:control",)
        )
        self.authority._require(owner, *permissions)

    def _live(self, command, execution):
        self._permissions(command["owner"], command["command"])
        if command["command"] in TERMINAL_COMMANDS and not self.terminal:
            raise Fault(403, "terminal_command_profile_disabled")
        if command["command"] in OWNER_COMMANDS and self.effects_fenced(execution["id"]):
            raise Fault(403, "terminal_intent_retained")
        self.authority._session(command["owner"], command["connection_id"])
        if (
            execution["lifecycle"] != "STARTING"
            or execution["control_state"] != "OWNED"
            or execution["authority_incarnation"] != self.store.incarnation
            or execution["owner"] != command["owner"]
            or execution["epoch"] != command["epoch"]
            or execution["connection_id"] != command["connection_id"]
            or execution["connection_generation"] != command["connection_generation"]
            or not execution["cap_hash"]
            or not hmac.compare_digest(execution["cap_hash"], command["controller_hash"])
            or self.authority.clock() >= command["expires_at"]
        ):
            raise Fault(403, "owner_command_controller_fenced")
        member = self.store.db.execute(
            "SELECT * FROM native_members WHERE execution_id=? AND target_id=?",
            (execution["id"], command["target_id"]),
        ).fetchone()
        if (
            member is None
            or member["state"] != "REGISTERED_UNPROVEN"
            or member["origin_hash"] != command["runtime_origin_hash"]
            or member["binding_hash"] != command["member_hash"]
        ):
            raise Fault(403, "owner_command_member_fenced")

    def enqueue(self, subject, key, payload):
        self.authority._require(subject, "execution:control")
        identifier(key)
        validate_owner_command_payload(payload, allow_terminal=self.terminal)
        self._permissions(subject, payload["command"])
        with self.authority._execution_lock(payload["execution_id"]):
            with self.store.transaction():
                self._permissions(subject, payload["command"])
                execution = self.authority._owner(subject, payload)
                if execution["lifecycle"] != "STARTING":
                    raise Fault(403, "owner_command_runtime_unavailable")
                # Native terminal admission is one-way. A new request ID must not
                # turn uncertainty into an automatic second physical attempt.
                if payload["command"] in OWNER_COMMANDS and self.effects_fenced(execution["id"]):
                    raise Fault(403, "terminal_intent_retained")
                # Live owner/session/policy proof precedes historical replay.
                replay = self.authority._replay(subject, "execution.command", key, payload)
                if replay is not None:
                    return replay
                member = self.store.db.execute(
                    "SELECT * FROM native_members WHERE execution_id=? AND target_id=? AND state='REGISTERED_UNPROVEN'",
                    (execution["id"], payload["target_admission_id"] or ""),
                ).fetchone()
                if member is None:
                    raise Fault(403, "owner_command_member_fenced")
                if (
                    self.store.db.execute("SELECT COUNT(*) FROM native_owner_commands").fetchone()[
                        0
                    ]
                    >= 4096
                    or self.store.db.execute(
                        "SELECT COUNT(*) FROM native_owner_commands WHERE execution_id=?",
                        (execution["id"],),
                    ).fetchone()[0]
                    >= 512
                    or self.store.db.execute(
                        "SELECT COUNT(*) FROM native_owner_commands WHERE execution_id=? AND state='QUEUED'",
                        (execution["id"],),
                    ).fetchone()[0]
                    >= 64
                ):
                    raise Fault(503, "owner_command_capacity")
                command_id = str(uuid.uuid4())
                operation = dict(
                    command_id=command_id,
                    target_admission_id=payload["target_admission_id"],
                    command=payload["command"],
                )
                values = dict(
                    command_id=command_id,
                    execution_id=execution["id"],
                    target_id=payload["target_admission_id"] or "",
                    owner=subject,
                    epoch=execution["epoch"],
                    connection_id=execution["connection_id"],
                    connection_generation=execution["connection_generation"],
                    controller_hash=execution["cap_hash"],
                    runtime_origin_hash=member["origin_hash"],
                    member_hash=member["binding_hash"],
                    command=payload["command"],
                    operation_digest=digest(operation),
                    expires_at=float(self.authority.clock() + 30),
                )
                self.store.db.execute(
                    "INSERT INTO native_owner_commands(command_id,execution_id,target_id,owner,epoch,connection_id,connection_generation,"
                    "controller_hash,runtime_origin_hash,member_hash,command,operation_digest,expires_at,state) VALUES("
                    ":command_id,:execution_id,:target_id,:owner,:epoch,:connection_id,:connection_generation,"
                    ":controller_hash,:runtime_origin_hash,:member_hash,:command,:operation_digest,:expires_at,'QUEUED')",
                    values,
                )
                self.store._event(
                    "OWNER_COMMAND_ADMITTED",
                    dict(
                        execution_id=execution["id"],
                        command_id=command_id,
                        command=payload["command"],
                        epoch=execution["epoch"],
                    ),
                )
                result = dict(
                    admitted=True,
                    execution_id=execution["id"],
                    command_id=command_id,
                    state="QUEUED",
                    quiescence_proven=False,
                    effective_transfer=False,
                    hold_retained=True,
                    runtime_enabled=False,
                )
                return self.authority._record(subject, "execution.command", key, payload, result)

    def poll(self, original):
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                execution = self.authority._original_grant(original)
                command = self.store.db.execute(
                    "SELECT * FROM native_owner_commands WHERE execution_id=? AND state='QUEUED' ORDER BY sequence LIMIT 1",
                    (original.execution_id,),
                ).fetchone()
                if command is None:
                    return dict(
                        action="none" if execution["control_state"] == "OWNED" else "hold",
                        execution_id=original.execution_id,
                    )
                try:
                    self._live(command, execution)
                    if command["runtime_origin_hash"] != FamilyAdmission.origin(original):
                        raise Fault(403, "owner_command_runtime_fenced")
                except Fault:
                    self.store.db.execute(
                        "UPDATE native_owner_commands SET state='DELIVERY_FENCED' WHERE command_id=?",
                        (command["command_id"],),
                    )
                    self.store._event(
                        "OWNER_COMMAND_DELIVERY_FENCED",
                        dict(execution_id=original.execution_id, command_id=command["command_id"]),
                    )
                    return dict(action="hold", execution_id=original.execution_id)
                token = secrets.token_hex(32)
                grant = OwnerCommandGrant(
                    "openbexi.owner-command/1",
                    self.store.incarnation,
                    original.execution_id,
                    execution["worker_slot"],
                    execution["worker_incarnation"],
                    execution["worker_generation"],
                    command["runtime_origin_hash"],
                    command["member_hash"],
                    command["owner"],
                    command["epoch"],
                    command["connection_id"],
                    command["connection_generation"],
                    command["command_id"],
                    command["target_id"] or None,
                    command["command"],
                    command["operation_digest"],
                    command["expires_at"],
                    token,
                )
                binding = asdict(grant)
                binding.pop("token")
                self.store.db.execute(
                    "UPDATE native_owner_commands SET state='DELIVERY_UNPROVEN',grant_hash=?,grant_binding=? WHERE command_id=?",
                    (secret_hash(token), canonical(binding).decode(), command["command_id"]),
                )
                self.store._event(
                    "OWNER_COMMAND_DELIVERED",
                    dict(execution_id=original.execution_id, command_id=command["command_id"]),
                )
                return dict(
                    action="command", execution_id=original.execution_id, grant=asdict(grant)
                )

    def _bound(self, original, grant):
        execution = self.authority._original_grant(original)
        if (
            original.execution_id != grant.execution_id
            or FamilyAdmission.origin(original) != grant.runtime_origin_hash
        ):
            raise Fault(403, "owner_command_runtime_fenced")
        command = self.store.db.execute(
            "SELECT * FROM native_owner_commands WHERE command_id=?", (grant.command_id,)
        ).fetchone()
        binding = asdict(grant)
        token = binding.pop("token")
        if (
            command is None
            or command["execution_id"] != original.execution_id
            or not command["grant_hash"]
            or not hmac.compare_digest(command["grant_hash"], secret_hash(token))
            or command["grant_binding"] != canonical(binding).decode()
        ):
            raise Fault(403, "owner_command_grant_fenced")
        return execution, command

    def advance(self, original, grant, stage):
        if grant.command in TERMINAL_COMMANDS and (not self.terminal or stage == "consume"):
            # Terminal authorization MUST occur at the CIF, before cancelPrompt
            # or setClosing, not at the later controller handler.
            raise Fault(403, "terminal_early_consumption_required")
        expected, state = {
            "forward": ("DELIVERY_UNPROVEN", "FORWARD_UNPROVEN"),
            "consume": ("FORWARD_UNPROVEN", "EXECUTION_UNPROVEN"),
        }[stage]
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                execution, command = self._bound(original, grant)
                self._live(command, execution)
                if command["state"] != expected:
                    raise Fault(409, "owner_command_phase_conflict")
                self.store.db.execute(
                    "UPDATE native_owner_commands SET state=? WHERE command_id=?",
                    (state, grant.command_id),
                )
                self.store._event(
                    "OWNER_COMMAND_" + stage.upper(),
                    dict(execution_id=original.execution_id, command_id=grant.command_id),
                )
                return self._receipt(grant, state)

    def effects_fenced(self, execution_id):
        """Retained terminal intent is a deny-only fence, never cleanup proof."""
        return (
            self.store.db.execute(
                "SELECT 1 FROM native_terminal_intents WHERE execution_id=? LIMIT 1",
                (execution_id,),
            ).fetchone()
            is not None
        )

    def consume_terminal(self, original, grant, native_status, prompt_id):
        """Atomic one-use authorization before the original CIF's first effect.

        Only the authenticated worker relay calls this, on a pinned original
        native Executor callback. Status/prompt values are not controller input.
        Cryptographic grant token + canonical binding, live owner, exact member,
        previous Context forwarding and SQL state consumption are all mandatory.
        """
        if not self.terminal or grant.command not in TERMINAL_COMMANDS:
            raise Fault(403, "terminal_command_profile_disabled")
        if type(native_status) is not str or native_status not in {
            "LOADED",
            "PAUSED",
            "RUNNING",
            "WAITING",
            "PROMPT",
            "INTERRUPTED",
            "FINISHED",
            "ERROR",
            "ABORTED",
        }:
            raise Fault(403, "terminal_native_status_invalid")
        if prompt_id is not None:
            canonical_uuid(prompt_id)
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                execution, command = self._bound(original, grant)
                self._live(command, execution)
                if command["state"] != "FORWARD_UNPROVEN":
                    raise Fault(409, "terminal_command_phase_conflict")
                if grant.command == "CMD_CLOSE":
                    if (
                        native_status not in {"FINISHED", "ERROR", "ABORTED"}
                        or prompt_id is not None
                    ):
                        raise Fault(409, "terminal_close_requires_terminal_state")
                elif native_status in {"FINISHED", "ERROR", "ABORTED"}:
                    raise Fault(409, "terminal_abort_already_terminal")
                prompts = self.authority.native_prompts
                if prompts is None:
                    raise Fault(403, "terminal_prompt_coordinator_required")
                pending = self.store.db.execute(
                    "SELECT * FROM native_prompts WHERE execution_id=? AND target_id=? AND state='OPEN'",
                    (original.execution_id, grant.target_admission_id or ""),
                ).fetchone()
                if (pending is None) != (prompt_id is None) or (
                    pending is not None
                    and (
                        pending["prompt_id"] != prompt_id
                        or pending["origin_hash"] != grant.runtime_origin_hash
                        or pending["member_hash"] != grant.member_binding_hash
                    )
                ):
                    raise Fault(403, "terminal_pending_prompt_mismatch")
                if native_status == "PROMPT" and prompt_id is None:
                    raise Fault(403, "terminal_pending_prompt_required")
                if self.store.db.execute(
                    "SELECT 1 FROM native_terminal_intents WHERE execution_id=? AND target_id=? AND command=?",
                    (original.execution_id, grant.target_admission_id or "", grant.command),
                ).fetchone():
                    raise Fault(409, "terminal_command_already_attempted")
                self.store.db.execute(
                    "INSERT INTO native_terminal_intents VALUES(?,?,?,?,?,?)",
                    (
                        grant.command_id,
                        original.execution_id,
                        grant.target_admission_id or "",
                        grant.command,
                        native_status,
                        prompt_id,
                    ),
                )
                changed = self.store.db.execute(
                    "UPDATE native_owner_commands SET state='EXECUTION_UNPROVEN' WHERE command_id=? AND state='FORWARD_UNPROVEN'",
                    (grant.command_id,),
                ).rowcount
                if changed != 1:
                    raise Fault(409, "terminal_command_phase_conflict")
                self.store._event(
                    "NATIVE_TERMINAL_ADMISSION_CONSUMED",
                    dict(
                        execution_id=original.execution_id,
                        command_id=grant.command_id,
                        command=grant.command,
                        native_status=native_status,
                        prompt_id=prompt_id,
                    ),
                )
                # No token is returned, and no hold, spent worker, owner or epoch
                # is changed. Lost acknowledgment cannot be retried or rebound.
                return self._receipt(grant, "EXECUTION_UNPROVEN")

    @staticmethod
    def _receipt(grant, state):
        return dict(
            command_id=grant.command_id,
            execution_id=grant.execution_id,
            state=state,
            operation_digest=grant.operation_digest,
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )

    def record_disposition(self, original, grant, disposition):
        """Record a real native mailbox outcome without settling execution effects.

        A returned command handler may have deferred work. This is a single
        authenticated post-consumption observation, never an effect permission.
        """
        if type(disposition) is not str or disposition not in {
            "DISCARDED_PENDING",
            "HANDLER_RETURNED",
        }:
            raise Fault(403, "owner_command_disposition_unqualified")
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                _execution, command = self._bound(original, grant)
                if command["state"] != "EXECUTION_UNPROVEN":
                    raise Fault(403, "owner_command_not_consumed")
                previous = self.store.db.execute(
                    "SELECT * FROM native_owner_command_dispositions WHERE command_id=?",
                    (grant.command_id,),
                ).fetchone()
                if previous is not None:
                    if (
                        previous["execution_id"] != original.execution_id
                        or previous["disposition"] != disposition
                    ):
                        raise Fault(409, "owner_command_disposition_conflict")
                else:
                    self.store.db.execute(
                        "INSERT INTO native_owner_command_dispositions VALUES(?,?,?)",
                        (grant.command_id, original.execution_id, disposition),
                    )
                    self.store._event(
                        "NATIVE_OWNER_COMMAND_MAILBOX_DISPOSITION",
                        dict(
                            execution_id=original.execution_id,
                            command_id=grant.command_id,
                            disposition=disposition,
                        ),
                    )
                return dict(
                    recorded=True,
                    command_id=grant.command_id,
                    execution_id=original.execution_id,
                    disposition=disposition,
                    state="EXECUTION_UNPROVEN",
                    quiescence_proven=False,
                    effective_transfer=False,
                    hold_retained=True,
                    runtime_enabled=False,
                )

    def report(self, original, grant, outcome):
        if type(outcome) is not str or outcome not in {"IPC_SEND_ACKNOWLEDGED", "UNCERTAIN"}:
            raise Fault(403, "owner_command_outcome_unqualified")
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                _execution, command = self._bound(original, grant)
                if command["diagnostic"] is not None and command["diagnostic"] != outcome:
                    raise Fault(409, "owner_command_report_conflict")
                if command["diagnostic"] is None:
                    self.store.db.execute(
                        "UPDATE native_owner_commands SET diagnostic=? WHERE command_id=?",
                        (outcome, grant.command_id),
                    )
                    self.store._event(
                        "OWNER_COMMAND_DISPATCH_REPORTED",
                        dict(
                            execution_id=original.execution_id,
                            command_id=grant.command_id,
                            outcome=outcome,
                        ),
                    )
                return self._receipt(grant, command["state"])
