"""Journal the private agent's first RUN for each admitted native member.

This does not intercept native internal commands or prove dequeue/settlement.
No failed call is retried, even with a newly generated request identifier.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import uuid

from openbexi_spell_server.contracts import canonical, digest
from openbexi_spell_server.family import FamilyAdmission
from openbexi_spell_server.launch import start_grant


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
        try:
            result = self.original(
                identifier, fields, context=context, send=send, procedure=procedure
            )
        except BaseException:
            try:
                self.report(operation, "UNCERTAIN")
            except Exception:
                pass  # The committed uncertain row survives a reporting outage.
            raise
        self.report(operation, "IPC_SEND_ACKNOWLEDGED")
        return result

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
