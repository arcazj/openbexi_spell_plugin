"""Private prompt-reply authorization candidate; not native execution qualification.

A prompt must be registered by the consumed worker and bound to its original
member. Replies are separately owner-authorized and single-delivery. Plaintext
answers exist in memory only, never in the durable ledger or audit. No receipt
proves a procedure/driver outcome, permits transfer or releases a hold.
"""

from dataclasses import asdict, dataclass, fields
import hmac
import math
import secrets
import uuid

from .authority import secret_hash
from .contracts import (
    AUTHORITY_FIELDS,
    Fault,
    canonical,
    digest,
    exact,
    fingerprint,
    identifier,
    validate_authority_payload,
)
from .family import FamilyAdmission
from .preflight import canonical_uuid


FLAGS = dict(
    quiescence_proven=False, effective_transfer=False, hold_retained=True, runtime_enabled=False
)


def answer_digest(action, answer):
    if type(action) is not str or action not in ("ANSWER", "CANCEL"):
        raise Fault(403, "prompt_action_unqualified")
    if action == "CANCEL":
        if answer is not None:
            raise Fault(400, "prompt_cancel_has_answer")
    else:
        if type(answer) is not str or "\x00" in answer:
            raise Fault(400, "prompt_answer_invalid")
        try:
            size = len(answer.encode("utf-8"))
        except UnicodeError as error:
            raise Fault(400, "prompt_answer_invalid") from error
        if size > 4096:
            raise Fault(413, "prompt_answer_too_large")
    return digest(dict(action=action, answer=answer))


def validate_reply_payload(body):
    proof = AUTHORITY_FIELDS["execution.start"]
    exact(
        body, proof | {"prompt_id", "target_admission_id", "definition_sha256", "action", "answer"}
    )
    validate_authority_payload("execution.start", {key: body[key] for key in proof})
    canonical_uuid(body["prompt_id"])
    if body["target_admission_id"] is not None:
        canonical_uuid(body["target_admission_id"])
    fingerprint(body["definition_sha256"])
    answer_digest(body["action"], body["answer"])


@dataclass(frozen=True)
class PromptReplyGrant:
    schema: str
    authority_incarnation: str
    execution_id: str
    worker_slot: str
    worker_incarnation: str
    worker_generation: int
    runtime_origin_hash: str
    member_binding_hash: str
    prompt_id: str
    target_admission_id: str | None
    definition_sha256: str
    reply_id: str
    owner: str
    control_epoch: int
    connection_id: str
    connection_generation: int
    action: str
    answer_sha256: str
    expires_at: float
    token: str


def prompt_grant(value):
    exact(value, {field.name for field in fields(PromptReplyGrant)})
    if value["schema"] != "openbexi.prompt-reply/1":
        raise Fault(403, "prompt_grant_schema_invalid")
    if type(value["action"]) is not str or value["action"] not in ("ANSWER", "CANCEL"):
        raise Fault(403, "prompt_action_unqualified")
    for key in ("authority_incarnation", "execution_id", "prompt_id", "reply_id", "connection_id"):
        canonical_uuid(value[key])
    if value["target_admission_id"] is not None:
        canonical_uuid(value["target_admission_id"])
    for key in ("worker_slot", "worker_incarnation", "owner"):
        identifier(value[key])
    for key in ("worker_generation", "control_epoch", "connection_generation"):
        if type(value[key]) is not int or not 1 <= value[key] < 2**63 - 1:
            raise Fault(400, "prompt_grant_generation_invalid")
    for key in (
        "runtime_origin_hash",
        "member_binding_hash",
        "definition_sha256",
        "answer_sha256",
        "token",
    ):
        fingerprint(value[key])
    if (
        type(value["expires_at"]) is not float
        or not math.isfinite(value["expires_at"])
        or not 0 < value["expires_at"] < 10**12
    ):
        raise Fault(400, "prompt_grant_deadline_invalid")
    return PromptReplyGrant(**value)


class NativePromptReplies:
    MAX_TOTAL = 4096
    MAX_PER_EXECUTION = 512

    def __init__(self, authority):
        self.authority, self.store = authority, authority.store
        if authority.native_controls is None or authority.native_prompts is not None:
            raise ValueError("Prompt replies require exactly one native member coordinator")
        # Values are retained only until one authorized worker delivery. They are
        # never reconstructed from storage or from a repeated owner request.
        self.answers: dict[str, str | None] = {}
        with self.store.transaction():
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_prompts("
                "prompt_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,target_id TEXT NOT NULL,"
                "instance_id TEXT NOT NULL,origin_hash TEXT NOT NULL,member_hash TEXT NOT NULL,"
                "definition_hash TEXT NOT NULL,state TEXT NOT NULL,outcome TEXT)"
            )
            self.store.db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_active_native_prompt "
                'ON native_prompts(execution_id,target_id) WHERE state="OPEN"'
            )
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_prompt_replies("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT,reply_id TEXT UNIQUE NOT NULL,"
                "prompt_id TEXT UNIQUE NOT NULL,execution_id TEXT NOT NULL,"
                "owner TEXT NOT NULL,epoch INTEGER NOT NULL,connection_id TEXT NOT NULL,"
                "connection_generation INTEGER NOT NULL,controller_hash TEXT NOT NULL,"
                "action TEXT NOT NULL,answer_hash TEXT NOT NULL,expires_at REAL NOT NULL,"
                "state TEXT NOT NULL,grant_hash TEXT,grant_binding TEXT,diagnostic TEXT)"
            )
            self.store.db.execute(
                'UPDATE native_prompts SET state="RESTART_FENCED" WHERE state="OPEN"'
            )
            self.store.db.execute(
                'UPDATE native_prompt_replies SET state="RESTART_FENCED" '
                'WHERE state!="RESTART_FENCED"'
            )
            if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 17:
                self.store.db.execute("PRAGMA user_version=17")
        authority.native_prompts = self

    def _member(self, execution_id, target_id, origin):
        member = self.store.db.execute(
            "SELECT * FROM native_members WHERE execution_id=? AND target_id=?",
            (execution_id, target_id or ""),
        ).fetchone()
        if (
            member is None
            or member["state"] != "REGISTERED_UNPROVEN"
            or member["origin_hash"] != origin
        ):
            raise Fault(403, "prompt_member_fenced")
        return member

    def _prompt(self, original, prompt_id):
        self.authority._original_grant(original)
        row = self.store.db.execute(
            "SELECT * FROM native_prompts WHERE prompt_id=?", (prompt_id,)
        ).fetchone()
        if (
            row is None
            or row["execution_id"] != original.execution_id
            or row["origin_hash"] != FamilyAdmission.origin(original)
        ):
            raise Fault(403, "prompt_origin_fenced")
        member = self._member(original.execution_id, row["target_id"], row["origin_hash"])
        if (
            member["binding_hash"] != row["member_hash"]
            or member["instance_id"] != row["instance_id"]
        ):
            raise Fault(403, "prompt_member_fenced")
        return row

    def register(self, original, body):
        prompt_id, target = body["prompt_id"], body["target_admission_id"]
        canonical_uuid(prompt_id)
        if target is not None:
            canonical_uuid(target)
        fingerprint(body["definition_sha256"])
        if type(body["instance_id"]) is not str or not 1 <= len(body["instance_id"]) <= 512:
            raise Fault(400, "prompt_instance_invalid")
        origin = FamilyAdmission.origin(original)
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                execution = self.authority._grant(original)
                if execution["lifecycle"] != "STARTING":
                    raise Fault(403, "prompt_runtime_unavailable")
                member = self._member(original.execution_id, target, origin)
                if member["instance_id"] != body["instance_id"]:
                    raise Fault(403, "prompt_member_fenced")
                if self.store.db.execute(
                    "SELECT 1 FROM native_prompts WHERE prompt_id=? OR "
                    '(execution_id=? AND target_id=? AND state="OPEN")',
                    (prompt_id, original.execution_id, target or ""),
                ).fetchone():
                    raise Fault(409, "prompt_already_registered")
                if (
                    self.store.db.execute("SELECT COUNT(*) FROM native_prompts").fetchone()[0]
                    >= self.MAX_TOTAL
                    or self.store.db.execute(
                        "SELECT COUNT(*) FROM native_prompts WHERE execution_id=?",
                        (original.execution_id,),
                    ).fetchone()[0]
                    >= self.MAX_PER_EXECUTION
                ):
                    raise Fault(503, "prompt_capacity_reached")
                self.store.db.execute(
                    'INSERT INTO native_prompts VALUES(?,?,?,?,?,?,?,"OPEN",NULL)',
                    (
                        prompt_id,
                        original.execution_id,
                        target or "",
                        body["instance_id"],
                        origin,
                        member["binding_hash"],
                        body["definition_sha256"],
                    ),
                )
                self.store._event(
                    "NATIVE_PROMPT_REGISTERED",
                    dict(
                        execution_id=original.execution_id,
                        prompt_id=prompt_id,
                    ),
                )
                return dict(
                    registered=True,
                    prompt_id=prompt_id,
                    execution_id=original.execution_id,
                    **FLAGS,
                )

    def enqueue(self, subject, key, payload):
        self.authority._require(subject, "execution:control", "execution:start")
        identifier(key)
        validate_reply_payload(payload)
        with self.authority._execution_lock(payload["execution_id"]):
            with self.store.transaction():
                self.authority._require(subject, "execution:control", "execution:start")
                execution = self.authority._owner(subject, payload)
                if execution["lifecycle"] != "STARTING":
                    raise Fault(403, "prompt_runtime_unavailable")
                replay = self.authority._replay(subject, "execution.prompt.reply", key, payload)
                if replay is not None:
                    return replay  # Admission history only; no answer or token.
                prompt = self.store.db.execute(
                    "SELECT * FROM native_prompts WHERE prompt_id=?", (payload["prompt_id"],)
                ).fetchone()
                if (
                    prompt is None
                    or prompt["execution_id"] != execution["id"]
                    or prompt["target_id"] != (payload["target_admission_id"] or "")
                    or prompt["definition_hash"] != payload["definition_sha256"]
                    or prompt["state"] != "OPEN"
                ):
                    raise Fault(403, "prompt_not_pending")
                member = self._member(execution["id"], prompt["target_id"], prompt["origin_hash"])
                if member["binding_hash"] != prompt["member_hash"]:
                    raise Fault(403, "prompt_member_fenced")
                if self.store.db.execute(
                    "SELECT 1 FROM native_prompt_replies WHERE prompt_id=?", (prompt["prompt_id"],)
                ).fetchone():
                    raise Fault(409, "prompt_reply_already_admitted")
                reply_id = str(uuid.uuid4())
                self.store.db.execute(
                    "INSERT INTO native_prompt_replies(reply_id,prompt_id,execution_id,owner,epoch,"
                    "connection_id,connection_generation,controller_hash,action,answer_hash,expires_at,state) "
                    'VALUES(?,?,?,?,?,?,?,?,?,?,?,"QUEUED")',
                    (
                        reply_id,
                        prompt["prompt_id"],
                        execution["id"],
                        subject,
                        execution["epoch"],
                        execution["connection_id"],
                        execution["connection_generation"],
                        execution["cap_hash"],
                        payload["action"],
                        answer_digest(payload["action"], payload["answer"]),
                        float(self.authority.clock() + 30),
                    ),
                )
                self.store._event(
                    "NATIVE_PROMPT_REPLY_ADMITTED",
                    dict(
                        execution_id=execution["id"],
                        prompt_id=prompt["prompt_id"],
                        reply_id=reply_id,
                    ),
                )
                result = dict(
                    admitted=True,
                    execution_id=execution["id"],
                    reply_id=reply_id,
                    prompt_id=prompt["prompt_id"],
                    state="QUEUED",
                    **FLAGS,
                )
                self.authority._record(subject, "execution.prompt.reply", key, payload, result)
            # Keep the execution lock until the memory-only value is installed.
            # Any crash here leaves an undeliverable, retained, non-replayable row.
            self.answers[reply_id] = payload["answer"]
            return result

    def _live(self, execution, prompt, reply):
        self.authority._require(reply["owner"], "execution:control", "execution:start")
        self.authority._session(reply["owner"], reply["connection_id"])
        if (
            execution["lifecycle"] != "STARTING"
            or execution["control_state"] != "OWNED"
            or execution["authority_incarnation"] != self.store.incarnation
            or execution["owner"] != reply["owner"]
            or execution["epoch"] != reply["epoch"]
            or execution["connection_id"] != reply["connection_id"]
            or execution["connection_generation"] != reply["connection_generation"]
            or not execution["cap_hash"]
            or not hmac.compare_digest(execution["cap_hash"], reply["controller_hash"])
            or self.authority.clock() >= reply["expires_at"]
            or prompt["state"] != "OPEN"
        ):
            raise Fault(403, "prompt_controller_or_generation_fenced")

    def poll(self, original):
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                execution = self.authority._original_grant(original)
                reply = self.store.db.execute(
                    'SELECT * FROM native_prompt_replies WHERE execution_id=? AND state="QUEUED" '
                    "ORDER BY sequence LIMIT 1",
                    (original.execution_id,),
                ).fetchone()
                if reply is None:
                    return dict(
                        action="none" if execution["control_state"] == "OWNED" else "hold",
                        execution_id=original.execution_id,
                    )
                try:
                    prompt = self._prompt(original, reply["prompt_id"])
                    self._live(execution, prompt, reply)
                    if reply["reply_id"] not in self.answers:
                        raise Fault(403, "prompt_value_unavailable")
                    answer = self.answers[reply["reply_id"]]
                    if answer_digest(reply["action"], answer) != reply["answer_hash"]:
                        raise Fault(403, "prompt_value_changed")
                except Fault:
                    self.store.db.execute(
                        'UPDATE native_prompt_replies SET state="DELIVERY_FENCED" WHERE reply_id=?',
                        (reply["reply_id"],),
                    )
                    result = dict(action="hold", execution_id=original.execution_id)
                    event = "NATIVE_PROMPT_REPLY_FENCED"
                else:
                    grant = PromptReplyGrant(
                        "openbexi.prompt-reply/1",
                        self.store.incarnation,
                        original.execution_id,
                        execution["worker_slot"],
                        execution["worker_incarnation"],
                        execution["worker_generation"],
                        prompt["origin_hash"],
                        prompt["member_hash"],
                        prompt["prompt_id"],
                        prompt["target_id"] or None,
                        prompt["definition_hash"],
                        reply["reply_id"],
                        reply["owner"],
                        reply["epoch"],
                        reply["connection_id"],
                        reply["connection_generation"],
                        reply["action"],
                        reply["answer_hash"],
                        float(reply["expires_at"]),
                        secrets.token_hex(32),
                    )
                    binding = asdict(grant)
                    token = binding.pop("token")
                    self.store.db.execute(
                        'UPDATE native_prompt_replies SET state="DELIVERY_UNPROVEN",grant_hash=?,'
                        "grant_binding=? WHERE reply_id=?",
                        (secret_hash(token), canonical(binding).decode(), reply["reply_id"]),
                    )
                    result = dict(
                        action="reply",
                        execution_id=original.execution_id,
                        grant=asdict(grant),
                        answer=answer,
                    )
                    event = "NATIVE_PROMPT_REPLY_DELIVERED"
                self.store._event(
                    event, dict(execution_id=original.execution_id, reply_id=reply["reply_id"])
                )
            self.answers.pop(reply["reply_id"], None)
            return result

    def _bound(self, original, grant):
        execution = self.authority._original_grant(original)
        prompt = self._prompt(original, grant.prompt_id)
        if (
            grant.execution_id != original.execution_id
            or grant.runtime_origin_hash != FamilyAdmission.origin(original)
        ):
            raise Fault(403, "prompt_grant_origin_fenced")
        reply = self.store.db.execute(
            "SELECT * FROM native_prompt_replies WHERE reply_id=?", (grant.reply_id,)
        ).fetchone()
        binding = asdict(grant)
        token = binding.pop("token")
        if (
            reply is None
            or reply["prompt_id"] != prompt["prompt_id"]
            or reply["execution_id"] != original.execution_id
            or not reply["grant_hash"]
            or not hmac.compare_digest(reply["grant_hash"], secret_hash(token))
            or reply["grant_binding"] != canonical(binding).decode()
        ):
            raise Fault(403, "prompt_grant_fenced")
        return execution, prompt, reply

    def advance(self, original, grant, stage):
        expected, next_state = {
            "forward": ("DELIVERY_UNPROVEN", "FORWARD_UNPROVEN"),
            "consume": ("FORWARD_UNPROVEN", "CONSUMED_UNPROVEN"),
        }[stage]
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                execution, prompt, reply = self._bound(original, grant)
                self._live(execution, prompt, reply)
                if reply["state"] != expected:
                    raise Fault(409, "prompt_phase_conflict")
                self.store.db.execute(
                    "UPDATE native_prompt_replies SET state=? WHERE reply_id=?",
                    (next_state, grant.reply_id),
                )
                self.store._event(
                    "NATIVE_PROMPT_REPLY_" + stage.upper(),
                    dict(
                        execution_id=original.execution_id,
                        prompt_id=grant.prompt_id,
                        reply_id=grant.reply_id,
                    ),
                )
                return dict(
                    reply_id=grant.reply_id,
                    prompt_id=grant.prompt_id,
                    execution_id=original.execution_id,
                    state=next_state,
                    **FLAGS,
                )

    def report(self, original, grant, outcome):
        if type(outcome) is not str or outcome not in {"IPC_SEND_ACKNOWLEDGED", "UNCERTAIN"}:
            raise Fault(403, "prompt_dispatch_outcome_unqualified")
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                _execution, _prompt, reply = self._bound(original, grant)
                if reply["state"] not in {
                    "FORWARD_UNPROVEN",
                    "CONSUMED_UNPROVEN",
                    "CLOSED_UNPROVEN",
                }:
                    raise Fault(403, "prompt_dispatch_not_forwarded")
                if reply["diagnostic"] is not None and reply["diagnostic"] != outcome:
                    raise Fault(409, "prompt_dispatch_report_conflict")
                if reply["diagnostic"] is None:
                    self.store.db.execute(
                        "UPDATE native_prompt_replies SET diagnostic=? WHERE reply_id=?",
                        (outcome, grant.reply_id),
                    )
                    self.store._event(
                        "NATIVE_PROMPT_DISPATCH_REPORTED",
                        dict(
                            execution_id=original.execution_id,
                            reply_id=grant.reply_id,
                            outcome=outcome,
                        ),
                    )
                return dict(
                    reply_id=grant.reply_id,
                    prompt_id=grant.prompt_id,
                    execution_id=original.execution_id,
                    state=reply["state"],
                    **FLAGS,
                )

    def close_prompt(self, original, body):
        canonical_uuid(body["prompt_id"])
        outcome = body["outcome"]
        if type(outcome) is not str or outcome not in {
            "ANSWER_SELECTED",
            "CANCEL_SELECTED",
            "TIMEOUT",
            "FAILED",
            "UNKNOWN",
        }:
            raise Fault(400, "prompt_close_outcome_invalid")
        with self.authority._execution_lock(original.execution_id):
            with self.store.transaction():
                prompt = self._prompt(original, body["prompt_id"])
                reply = self.store.db.execute(
                    "SELECT * FROM native_prompt_replies WHERE prompt_id=?", (body["prompt_id"],)
                ).fetchone()
                if prompt["state"] == "CLOSED":
                    if prompt["outcome"] != outcome:
                        raise Fault(409, "prompt_close_conflict")
                elif prompt["state"] != "OPEN":
                    raise Fault(403, "prompt_not_pending")
                else:
                    if outcome in ("ANSWER_SELECTED", "CANCEL_SELECTED"):
                        action = "ANSWER" if outcome == "ANSWER_SELECTED" else "CANCEL"
                        if (
                            reply is None
                            or reply["state"] != "CONSUMED_UNPROVEN"
                            or reply["action"] != action
                        ):
                            raise Fault(403, "prompt_close_not_consumed")
                    self.store.db.execute(
                        'UPDATE native_prompts SET state="CLOSED",outcome=? WHERE prompt_id=?',
                        (outcome, prompt["prompt_id"]),
                    )
                    if reply is not None and reply["state"] != "CONSUMED_UNPROVEN":
                        self.store.db.execute(
                            'UPDATE native_prompt_replies SET state="CLOSED_UNPROVEN" WHERE reply_id=?',
                            (reply["reply_id"],),
                        )
                    self.store._event(
                        "NATIVE_PROMPT_CLOSED",
                        dict(
                            execution_id=original.execution_id,
                            prompt_id=prompt["prompt_id"],
                            outcome=outcome,
                        ),
                    )
            if reply is not None:
                self.answers.pop(reply["reply_id"], None)
            return dict(
                recorded=True,
                prompt_id=prompt["prompt_id"],
                outcome=outcome,
                execution_id=original.execution_id,
                **FLAGS,
            )
