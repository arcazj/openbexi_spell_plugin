"""Journal the private agent's first RUN for each admitted native member.

This does not intercept native internal commands or prove dequeue/settlement.
No failed call is retried, even with a newly generated request identifier.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import uuid

from openbexi_spell_server.contracts import canonical, digest, exact
from openbexi_spell_server.family import FamilyAdmission
from openbexi_spell_server.launch import start_grant
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
        self.lock = threading.Lock()

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

    def forward(self, body):
        """Authenticated native Context callback, before its Executor IPC send."""
        exact(body, {"schema", "request_id", "instance_id", "command"})
        canonical_uuid(body["request_id"])
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
