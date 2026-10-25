"""Journal the private agent's first RUN for each admitted native member.

The private candidate routes initial automatic RUNs through final consumption.
This does not settle execution or intercept all other native mutation paths.
No failed call is retried, even with a newly generated request identifier.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import uuid
from dataclasses import asdict

from openbexi_spell_server.contracts import canonical, digest, exact
from openbexi_spell_server.family import FamilyAdmission
from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.commands import owner_command_grant
from openbexi_spell_server.preflight import canonical_uuid


class NativeRunJournal:
    def __init__(self, session, request, route, children):
        self.session, self.request, self.route, self.children = (
            session,
            request,
            route,
            children,
        )
        self.original = session.request
        self.grant = start_grant(request["grant"])
        self.attempted = set()
        self.operations = {}
        self.forward_attempted = set()
        self.forwarded = set()
        self.consume_attempted = set()
        self.consumed = set()
        self.member_attempted = set()
        self.bound_members = {}
        self.owner_operations = {}
        self.owner_forward_attempted = set()
        self.owner_forwarded = set()
        self.owner_consume_attempted = set()
        self.owner_consumed = set()
        self.disposition_attempted = set()
        self.lock = threading.Lock()

    def bind_member(self, instance, pid, parent_pid, start_ticks, executable_sha256):
        with self.lock:
            if instance in self.member_attempted or len(self.member_attempted) >= 65:
                raise ValueError("Native member already attempted or capacity reached")
            with self.children.lock:
                if instance not in self.children.started:
                    raise ValueError("Native member was not admitted")
                target = self.children.started[instance]
            # A lost registration reply cannot authorize a replacement binding.
            self.member_attempted.add(instance)
        fields = dict(
            target_admission_id=target,
            instance_id=instance,
            pid=pid,
            parent_pid=parent_pid,
            start_ticks=start_ticks,
            executable_sha256=executable_sha256,
        )
        reply = self.route.call(
            {**self.request, **fields},
            path="/v1/worker/member-bind",
            schema="openbexi.worker/2",
        )
        expected = dict(
            registered=True,
            execution_id=self.grant.execution_id,
            **fields,
            origin_hash=FamilyAdmission.origin(self.grant),
            binding_hash=digest(fields),
            state="REGISTERED_UNPROVEN",
            host_attested=False,
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if canonical(reply) != canonical(expected):
            raise ValueError("Native member registration receipt differs")
        with self.lock:
            self.bound_members[instance] = digest(fields)

    def dispatch(
        self, identifier, fields=None, *, context=False, send=False, procedure=None
    ):
        if identifier != "CMD_RUN":
            return self.original(
                identifier, fields, context=context, send=send, procedure=procedure
            )
        target = self.session.instance if procedure is None else procedure
        if context is not False or send is not True or fields not in (None, {}):
            raise ValueError("Only the exact initial native RUN is qualified")
        with self.lock:
            if target in self.attempted or len(self.attempted) >= 65:
                raise ValueError("Native RUN already attempted or capacity reached")
            # Retain locally before either RPC or IPC, including a lost admission.
            self.attempted.add(target)
            with self.children.lock:
                if target not in self.children.started:
                    raise ValueError("Native RUN target was not admitted")
                admission = self.children.started[target]
        operation = dict(
            request_id=str(uuid.uuid4()),
            target_admission_id=admission,
            command=identifier,
        )
        reply = self.route.call(
            {**self.request, **operation},
            path="/v1/worker/control-admit",
            schema="openbexi.worker/2",
        )
        expected = dict(
            admitted=True,
            execution_id=self.grant.execution_id,
            **operation,
            origin_hash=FamilyAdmission.origin(self.grant),
            operation_digest=digest(operation),
            state="DISPATCH_UNCERTAIN",
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if canonical(reply) != canonical(expected):
            raise ValueError("Native RUN admission receipt differs")
        with self.lock:
            self.operations[operation["request_id"]] = (target, operation)
        try:
            result = self.original(
                identifier,
                {"V08ControlRequest": operation["request_id"]},
                context=context,
                send=send,
                procedure=procedure,
            )
        except BaseException:
            try:
                self.report(operation, "UNCERTAIN")
            except Exception:
                pass  # The committed uncertain row survives a reporting outage.
            raise
        self.report(operation, "IPC_SEND_ACKNOWLEDGED")
        return result

    def poll_owner(self):
        reply = self.route.call(
            self.request, path="/v1/worker/command-poll", schema="openbexi.worker/2"
        )
        if (
            type(reply) is not dict
            or reply.get("execution_id") != self.grant.execution_id
            or type(reply.get("action")) is not str
        ):
            raise ValueError("Owner command delivery scope differs")
        if reply.get("action") in {"none", "hold"}:
            exact(reply, {"action", "execution_id"})
            return reply["action"]
        exact(reply, {"action", "execution_id", "grant"})
        if reply["action"] != "command":
            raise ValueError("Owner command delivery action differs")
        self.dispatch_owner(reply["grant"])
        return "command"

    def dispatch_owner(self, value):
        grant = owner_command_grant(value)
        if any(
            getattr(grant, key) != getattr(self.grant, key)
            for key in (
                "authority_incarnation",
                "execution_id",
                "worker_slot",
                "worker_incarnation",
                "worker_generation",
            )
        ) or grant.runtime_origin_hash != FamilyAdmission.origin(self.grant):
            raise ValueError("Owner command runtime identity differs")
        operation = dict(
            command_id=grant.command_id,
            target_admission_id=grant.target_admission_id,
            command=grant.command,
        )
        if digest(operation) != grant.operation_digest:
            raise ValueError("Owner command operation differs")
        with self.lock:
            if (
                grant.command_id in self.owner_operations
                or grant.command_id in self.operations
                or len(self.owner_operations) >= 512
            ):
                raise ValueError("Owner command already attempted or capacity reached")
            with self.children.lock:
                targets = [
                    instance
                    for instance, admission in self.children.started.items()
                    if admission == grant.target_admission_id
                ]
            if (
                len(targets) != 1
                or self.bound_members.get(targets[0]) != grant.member_binding_hash
            ):
                raise ValueError("Owner command member binding differs")
            target = targets[0]
            self.owner_operations[grant.command_id] = (target, grant)
        try:
            result = self.original(
                grant.command,
                {"V08ControlRequest": grant.command_id},
                send=True,
                procedure=target,
            )
        except BaseException:
            try:
                self.report_owner(grant, "UNCERTAIN")
            except Exception:
                pass
            raise
        self.report_owner(grant, "IPC_SEND_ACKNOWLEDGED")
        return result

    def report_owner(self, grant, outcome):
        reply = self.route.call(
            {**self.request, "command_grant": asdict(grant), "outcome": outcome},
            path="/v1/worker/command-report",
            schema="openbexi.worker/2",
        )
        self._owner_receipt(
            grant,
            reply,
            {"DELIVERY_UNPROVEN", "FORWARD_UNPROVEN", "EXECUTION_UNPROVEN"},
        )

    @staticmethod
    def _owner_receipt(grant, reply, states):
        if (
            type(reply) is not dict
            or type(reply.get("state")) is not str
            or reply["state"] not in states
        ):
            raise ValueError("Owner command receipt state differs")
        expected = dict(
            command_id=grant.command_id,
            execution_id=grant.execution_id,
            state=reply["state"],
            operation_digest=grant.operation_digest,
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if canonical(reply) != canonical(expected):
            raise ValueError("Owner command receipt differs")

    def _owner_phase(self, body, stage):
        expected_schema = (
            "openbexi.native-control/1"
            if stage == "forward"
            else "openbexi.native-consume/1"
        )
        with self.lock:
            target, grant = self.owner_operations[body["request_id"]]
            if (
                body["schema"] != expected_schema
                or body["instance_id"] != target
                or body["command"] != grant.command
            ):
                raise ValueError("Owner command callback identity differs")
            attempts = (
                self.owner_forward_attempted
                if stage == "forward"
                else self.owner_consume_attempted
            )
            if grant.command_id in attempts:
                raise ValueError("Owner command callback already attempted")
            if stage == "consume" and grant.command_id not in self.owner_forwarded:
                raise ValueError("Owner command forwarding was not verified")
            attempts.add(grant.command_id)
        reply = self.route.call(
            {**self.request, "command_grant": asdict(grant)},
            path="/v1/worker/command-" + stage,
            schema="openbexi.worker/2",
        )
        self._owner_receipt(
            grant,
            reply,
            {"FORWARD_UNPROVEN" if stage == "forward" else "EXECUTION_UNPROVEN"},
        )
        with self.lock:
            (self.owner_forwarded if stage == "forward" else self.owner_consumed).add(
                grant.command_id
            )

    def forward(self, body):
        """Authenticated native Context callback, before its Executor IPC send."""
        exact(body, {"schema", "request_id", "instance_id", "command"})
        canonical_uuid(body["request_id"])
        if body["request_id"] in self.owner_operations:
            return self._owner_phase(body, "forward")
        if (
            body["schema"] != "openbexi.native-control/1"
            or body["command"] != "CMD_RUN"
        ):
            raise ValueError("Native control schema/command differs")
        with self.lock:
            known = self.operations.get(body["request_id"])
            if (
                known is None
                or type(body["instance_id"]) is not str
                or known[0] != body["instance_id"]
            ):
                raise ValueError("Native RUN forwarding identity was not admitted")
            if body["request_id"] in self.forward_attempted:
                raise ValueError("Native RUN forwarding already attempted")
            self.forward_attempted.add(body["request_id"])
            operation = known[1]
        reply = self.route.call(
            {**self.request, **operation},
            path="/v1/worker/control-forward",
            schema="openbexi.worker/2",
        )
        expected = dict(
            forward_admitted=True,
            execution_id=self.grant.execution_id,
            **operation,
            origin_hash=FamilyAdmission.origin(self.grant),
            operation_digest=digest(operation),
            state="FORWARD_UNPROVEN",
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if canonical(reply) != canonical(expected):
            raise ValueError("Native RUN forwarding receipt differs")
        with self.lock:
            self.forwarded.add(body["request_id"])

    def consume(self, body):
        """Authenticated, registered native Executor callback before executing RUN."""
        exact(body, {"schema", "request_id", "instance_id", "command"})
        canonical_uuid(body["request_id"])
        if body["request_id"] in self.owner_operations:
            return self._owner_phase(body, "consume")
        if (
            body["schema"] != "openbexi.native-consume/1"
            or body["command"] != "CMD_RUN"
        ):
            raise ValueError("Native control schema/command differs")
        with self.lock:
            known = self.operations.get(body["request_id"])
            if (
                known is None
                or body["request_id"] not in self.forwarded
                or type(body["instance_id"]) is not str
                or known[0] != body["instance_id"]
            ):
                raise ValueError("Native RUN consumption identity was not admitted")
            if body["request_id"] in self.consume_attempted:
                raise ValueError("Native RUN consumption already attempted")
            self.consume_attempted.add(body["request_id"])
            operation = known[1]
        reply = self.route.call(
            {**self.request, **operation},
            path="/v1/worker/control-consume",
            schema="openbexi.worker/2",
        )
        expected = dict(
            consume_admitted=True,
            execution_id=self.grant.execution_id,
            **operation,
            origin_hash=FamilyAdmission.origin(self.grant),
            operation_digest=digest(operation),
            state="EXECUTION_UNPROVEN",
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if canonical(reply) != canonical(expected):
            raise ValueError("Native RUN consumption receipt differs")
        with self.lock:
            self.consumed.add(body["request_id"])

    def disposition(self, body):
        """Single attempt from a real Executor after mailbox handler/discard."""
        exact(body, {"schema", "request_id", "instance_id", "command", "disposition"})
        if body["schema"] != "openbexi.native-disposition/1":
            raise ValueError("Native disposition schema differs")
        canonical_uuid(body["request_id"])
        if type(body["disposition"]) is not str or body["disposition"] not in {
            "DISCARDED_PENDING",
            "HANDLER_RETURNED",
        }:
            raise ValueError("Native disposition not recognized")
        with self.lock:
            request_id = body["request_id"]
            if request_id in self.disposition_attempted:
                raise ValueError("Native disposition already attempted")
            if request_id in self.owner_operations:
                instance, grant = self.owner_operations[request_id]
                if (
                    instance != body["instance_id"]
                    or grant.command != body["command"]
                    or request_id not in self.owner_consumed
                ):
                    raise ValueError("Native owner disposition scope differs")
                payload = {
                    **self.request,
                    "command_grant": asdict(grant),
                    "disposition": body["disposition"],
                }
                path = "/v1/worker/command-disposition"
                owner = True
            else:
                operation = self.operations.get(request_id)
                if (
                    operation is None
                    or operation[0] != body["instance_id"]
                    or operation[1]["command"] != body["command"]
                    or request_id not in self.consumed
                ):
                    raise ValueError("Native initial disposition scope differs")
                payload = {
                    **self.request,
                    **operation[1],
                    "disposition": body["disposition"],
                }
                path = "/v1/worker/control-disposition"
                owner = False
            self.disposition_attempted.add(request_id)
        reply = self.route.call(payload, path=path, schema="openbexi.worker/2")
        expected = dict(
            recorded=True,
            request_id=request_id,
            execution_id=self.grant.execution_id,
            disposition=body["disposition"],
            state="EXECUTION_UNPROVEN",
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if owner:
            expected["command_id"] = expected.pop("request_id")
        if canonical(reply) != canonical(expected):
            raise ValueError("Native mailbox disposition receipt differs")

    def report(self, operation, outcome):
        reply = self.route.call(
            {**self.request, **operation, "outcome": outcome},
            path="/v1/worker/control-report",
            schema="openbexi.worker/2",
        )
        expected = dict(
            recorded=True,
            request_id=operation["request_id"],
            execution_id=self.grant.execution_id,
            outcome=outcome,
            state="DISPATCH_UNCERTAIN",
            quiescence_proven=False,
            effective_transfer=False,
            hold_retained=True,
            runtime_enabled=False,
        )
        if canonical(reply) != canonical(expected):
            raise ValueError("Native RUN transport receipt differs")
