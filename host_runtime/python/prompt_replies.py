"""Private native prompt relay, disabled unless explicitly provisioned.

The prompt-enabled source build and trusted worker profile must both be selected.
Public Gateway/Listener control remains disabled. Native system acceptance,
ABORT/CLOSE and terminal cleanup remain separate Step 1 requirements.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import asdict
import threading

from openbexi_spell_server.contracts import canonical, digest, exact, fingerprint
from openbexi_spell_server.family import FamilyAdmission
from openbexi_spell_server.preflight import canonical_uuid
from openbexi_spell_server.prompts import FLAGS, answer_digest, prompt_grant


class NativePromptAgent:
    def __init__(self, journal):
        self.journal = journal
        self.original = journal.grant
        self.lock = threading.Lock()
        self.registrations = {}  # Retained tombstones; never reuse a prompt ID.
        self.active = {}
        self.open_attempted = set()
        self.replies = {}  # Grants and bindings only; no retained answer values.
        self.forwarded = set()
        self.consume_attempted = set()
        self.close_attempted = set()

    def _member(self, instance):
        with self.journal.lock:
            with self.journal.children.lock:
                if instance not in self.journal.children.started:
                    raise ValueError("Prompt member was not admitted")
                target = self.journal.children.started[instance]
            binding = self.journal.bound_members.get(instance)
            if binding is None:
                raise ValueError("Prompt member was not registered")
            return target, binding

    def _call(self, path, fields):
        return self.journal.route.call(
            {**self.journal.request, **fields},
            path="/v1/worker/" + path,
            schema="openbexi.worker/2",
        )

    def declare(self, body):
        """Digest the actual native definition, received from its pinned process.

        It is transient only: register() sends just the digest to Context.
        No caller-supplied digest can substitute for these native fields.
        """
        exact(body, {"schema", "instance_id", "prompt_id", "definition"})
        if body["schema"] != "openbexi.native-prompt-declare/1":
            raise ValueError("Native prompt declaration schema differs")
        fields = body["definition"]
        if (
            type(fields) is not dict
            or not 1 <= len(fields) <= 32
            or any(
                type(key) is not str
                or type(value) is not str
                or not 1 <= len(key) <= 64
                or "\x00" in key
                or "\x00" in value
                or key.startswith("V08")
                for key, value in fields.items()
            )
            or type(body["instance_id"]) is not str
            or fields.get("ProcId") != body["instance_id"]
            or len(canonical(fields)) > 16384
        ):
            raise ValueError("Native prompt definition differs or exceeds bounds")
        self.register(
            dict(
                schema="openbexi.native-prompt-open/1",
                instance_id=body["instance_id"],
                prompt_id=body["prompt_id"],
                definition_sha256=digest(fields),
            )
        )

    def register(self, body):
        exact(body, {"schema", "instance_id", "prompt_id", "definition_sha256"})
        if body["schema"] != "openbexi.native-prompt-open/1":
            raise ValueError("Native prompt schema differs")
        canonical_uuid(body["prompt_id"])
        fingerprint(body["definition_sha256"])
        if type(body["instance_id"]) is not str:
            raise ValueError("Native prompt instance differs")
        prompt_id, instance = body["prompt_id"], body["instance_id"]
        with self.lock:
            target, binding = self._member(instance)
            if prompt_id in self.open_attempted or instance in self.active:
                raise ValueError(
                    "Native prompt already attempted or member still pending"
                )
            if len(self.open_attempted) >= 512:
                raise ValueError("Native prompt capacity reached")
            self.open_attempted.add(prompt_id)
            # Retain a pending identity even if registration acknowledgment is lost.
            self.active[instance] = prompt_id
        result = self._call(
            "prompt-open",
            dict(
                prompt_id=prompt_id,
                instance_id=instance,
                target_admission_id=target,
                definition_sha256=body["definition_sha256"],
            ),
        )
        expected = dict(
            registered=True,
            prompt_id=prompt_id,
            execution_id=self.original.execution_id,
            **FLAGS,
        )
        if canonical(result) != canonical(expected):
            raise ValueError("Native prompt registration receipt differs")
        with self.lock:
            self.registrations[prompt_id] = (
                instance,
                target,
                binding,
                body["definition_sha256"],
            )

    def poll(self):
        # Only a registered native prompt can receive a reply. Do not contend
        # with declarations/consumption using idle TLS/SQL polls for an empty
        # local prompt inventory. This is not an authority or effect decision.
        with self.lock:
            if not self.active:
                return "none"
        result = self._call("prompt-poll", {})
        if (
            type(result) is not dict
            or result.get("execution_id") != self.original.execution_id
        ):
            raise ValueError("Native prompt delivery scope differs")
        if result.get("action") in ("none", "hold"):
            exact(result, {"action", "execution_id"})
            return result["action"]
        exact(result, {"action", "execution_id", "grant", "answer"})
        if result["action"] != "reply":
            raise ValueError("Native prompt delivery action differs")
        self.dispatch(result["grant"], result["answer"])
        return "reply"

    @staticmethod
    def _receipt(grant, result, state):
        expected = dict(
            reply_id=grant.reply_id,
            prompt_id=grant.prompt_id,
            execution_id=grant.execution_id,
            state=state,
            **FLAGS,
        )
        if canonical(result) != canonical(expected):
            raise ValueError("Native prompt authority receipt differs")

    def _pending(self, grant):
        registration = self.registrations.get(grant.prompt_id)
        if registration is None:
            raise ValueError("Native prompt was not registered")
        instance, target, binding, definition = registration
        if (
            self.active.get(instance) != grant.prompt_id
            or target != grant.target_admission_id
            or binding != grant.member_binding_hash
            or definition != grant.definition_sha256
            or self._member(instance) != (target, binding)
        ):
            raise ValueError("Native prompt member or generation differs")
        return instance

    def dispatch(self, value, answer):
        grant = prompt_grant(value)
        if (
            any(
                getattr(grant, key) != getattr(self.original, key)
                for key in (
                    "authority_incarnation",
                    "execution_id",
                    "worker_slot",
                    "worker_incarnation",
                    "worker_generation",
                    "control_epoch",
                    "connection_id",
                    "connection_generation",
                )
            )
            or grant.runtime_origin_hash != FamilyAdmission.origin(self.original)
            or answer_digest(grant.action, answer) != grant.answer_sha256
        ):
            raise ValueError("Native prompt reply provenance or answer differs")
        with self.lock:
            instance = self._pending(grant)
            if grant.reply_id in self.replies or len(self.replies) >= 512:
                raise ValueError(
                    "Native prompt reply already attempted or capacity reached"
                )
            self.replies[grant.reply_id] = (instance, grant)
        result = self._call("prompt-forward", {"prompt_grant": asdict(grant)})
        self._receipt(grant, result, "FORWARD_UNPROVEN")
        with self.lock:
            if self._pending(grant) != instance:
                raise ValueError("Native prompt changed before forwarding")
            self.forwarded.add(grant.reply_id)
        # No lock spans IPC. A synchronous native consume callback must be able
        # to run. Its own pending-prompt lock and final Context check are required.
        fields = {"V08PromptId": grant.prompt_id, "V08PromptRequest": grant.reply_id}
        if grant.action == "ANSWER":
            fields["ReturnValue"] = answer
        try:
            self.journal.original(
                "MSG_ANSWER" if grant.action == "ANSWER" else "MSG_CANCEL",
                fields,
                send=True,
                procedure=instance,
            )
        except BaseException:
            try:
                self.report(grant, "UNCERTAIN")
            except Exception:
                pass  # The committed forward/consume row stays unproven.
            raise
        self.report(grant, "IPC_SEND_ACKNOWLEDGED")
        # IPC send success is not selected-answer, abort, or terminal-effect proof.

    def report(self, grant, outcome):
        result = self._call(
            "prompt-report",
            {
                "prompt_grant": asdict(grant),
                "outcome": outcome,
            },
        )
        if type(result) is not dict or result.get("state") not in {
            "FORWARD_UNPROVEN",
            "CONSUMED_UNPROVEN",
            "CLOSED_UNPROVEN",
        }:
            raise ValueError("Native prompt dispatch state differs")
        self._receipt(grant, result, result["state"])

    def consume(self, body):
        exact(
            body, {"schema", "instance_id", "prompt_id", "reply_id", "action", "answer"}
        )
        if body["schema"] != "openbexi.native-prompt-consume/1":
            raise ValueError("Native prompt consumption schema differs")
        canonical_uuid(body["prompt_id"])
        canonical_uuid(body["reply_id"])
        hashed = answer_digest(body["action"], body["answer"])
        with self.lock:
            operation = self.replies.get(body["reply_id"])
            if operation is None:
                raise ValueError("Native prompt reply not delivered")
            instance, grant = operation
            if (
                instance != body["instance_id"]
                or grant.prompt_id != body["prompt_id"]
                or grant.action != body["action"]
                or grant.answer_sha256 != hashed
                or grant.reply_id not in self.forwarded
                or self._pending(grant) != instance
            ):
                raise ValueError("Native prompt consumption binding differs")
            if grant.reply_id in self.consume_attempted:
                raise ValueError("Native prompt consumption already attempted")
            self.consume_attempted.add(grant.reply_id)
        result = self._call("prompt-consume", {"prompt_grant": asdict(grant)})
        self._receipt(grant, result, "CONSUMED_UNPROVEN")

    def close(self, body):
        exact(body, {"schema", "instance_id", "prompt_id", "outcome"})
        if body["schema"] != "openbexi.native-prompt-close/1":
            raise ValueError("Native prompt close schema differs")
        canonical_uuid(body["prompt_id"])
        if type(body["outcome"]) is not str or body["outcome"] not in {
            "ANSWER_SELECTED",
            "CANCEL_SELECTED",
            "TIMEOUT",
            "FAILED",
            "UNKNOWN",
        }:
            raise ValueError("Native prompt outcome differs")
        with self.lock:
            registration = self.registrations.get(body["prompt_id"])
            if (
                registration is None
                or registration[0] != body["instance_id"]
                or self.active.get(body["instance_id"]) != body["prompt_id"]
                or self._member(body["instance_id"]) != registration[1:3]
            ):
                raise ValueError("Native prompt close binding differs")
            if body["prompt_id"] in self.close_attempted:
                raise ValueError("Native prompt close already attempted")
            self.close_attempted.add(body["prompt_id"])
        result = self._call(
            "prompt-close", {"prompt_id": body["prompt_id"], "outcome": body["outcome"]}
        )
        expected = dict(
            recorded=True,
            prompt_id=body["prompt_id"],
            outcome=body["outcome"],
            execution_id=self.original.execution_id,
            **FLAGS,
        )
        if canonical(result) != canonical(expected):
            raise ValueError("Native prompt close receipt differs")
        with self.lock:
            del self.active[body["instance_id"]]
