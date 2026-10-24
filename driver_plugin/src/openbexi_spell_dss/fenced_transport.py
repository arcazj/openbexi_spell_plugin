"""Private v0.8 Context transport; every command requires a bound effect admission.

Derived from the original GPL DSS transport. Legacy transport and its immutable
patch preimages remain unchanged. This adapter does not expose a worker route.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import socket
import time
import threading
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

from dss.catalog import canonical
from dss.packets import decode_packet, decode_tm, encode_tc, recv_packet
from .journal import UncertainEffect
from .transport import Transport as LegacyTransport


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        response.close()
        raise ValueError("DSS metadata redirects are not permitted")


class Transport(LegacyTransport):
    def __init__(self, *args, **kwargs):
        # One Context-owned instance per binding. Do not overload the legacy
        # four-handler metadata API when ten executions begin together.
        self.metadata_admission = threading.BoundedSemaphore(1)
        super().__init__(*args, **kwargs)

    def get(self, path):
        # Keep every read on the operator's fixed endpoint. Neither a DSS 3xx
        # nor environment proxy settings may select another network authority.
        if path not in {"state", "telemetry"}:
            raise ValueError("DSS metadata path is not permitted")
        opener = build_opener(ProxyHandler({}), NoRedirect())
        request = Request(
            self.url + "/api/v1/" + path, headers={"Accept": "application/json"}
        )
        try:
            response = opener.open(request, timeout=3)
        except HTTPError as error:
            error.close()
            raise
        with response:
            raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError("DSS response bound exceeded")
            return json.loads(raw)

    def current_state(self):
        if not self.metadata_admission.acquire(timeout=0.25):
            raise TimeoutError("DSS metadata admission busy; no effect attempted")
        try:
            return self.get("state")
        finally:
            self.metadata_admission.release()

    def command(
        self, name, arguments, identity, operation, check, *, admission, timeout=5
    ):
        identity = dict(identity)
        admission.validate(identity, operation)
        arguments = self.arguments(name, arguments)
        state = self.current_state()
        if state["epoch"] != self.epoch or state["scenario_id"] != self.scenario:
            raise ValueError("DSS epoch changed; explicit rebinding required")
        digest = hashlib.sha256(
            canonical(
                dict(
                    command_name=name,
                    arguments=arguments,
                    database_digest=self.database.digest,
                )
            )
        ).hexdigest()
        base = dict(
            schema_version="openbexi.dss.tc/1",
            satellite_id="GENERIC",
            database_revision=self.database.revision,
            database_digest=self.database.digest,
            satellite_epoch=self.epoch,
            scenario_id=self.scenario,
            operation_id=operation,
            procedure_id=identity["definition"],
            execution_id=identity["procedure"],
            plan_id=operation,
            element_id="command-1",
            command_name=name,
            arguments=arguments,
            command_digest=digest,
        )
        receipts, sent = [], False
        deadline = time.monotonic() + timeout
        stages = [
            ("TRANSPORT", "ACCEPTED"),
            ("LOADING", "LOADED"),
            ("RELEASE", "RELEASED"),
            ("ACKNOWLEDGEMENT", "ACKNOWLEDGED"),
            ("ONBOARD_EXECUTION", "SUCCEEDED"),
        ]
        try:
            with socket.create_connection(self.tc_address, timeout=2) as connection:
                for sequence, (stage, expected) in enumerate(stages):
                    check()  # Live parent authority is checked before EVERY write.
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Command deadline expired")
                    connection.settimeout(min(3, remaining))
                    packet_bytes = encode_tc(dict(base, stage=stage), sequence)
                    # The Context adapter owns the final check AND socket write.
                    # Receipt waiting/decoding remains outside its execution mutex.
                    sent = True  # A failed write can have sent a prefix.
                    admission.send(stage, connection, packet_bytes)
                    raw = recv_packet(
                        connection,
                        timeout=min(3, max(0.001, deadline - time.monotonic())),
                    )
                    packet = decode_packet(raw)
                    answer = decode_tm(raw)
                    if (
                        packet.apid != 102
                        or answer.get("schema_version") != "openbexi.dss.ack/1"
                        or any(
                            answer.get(key) != value
                            for key, value in base.items()
                            if key not in {"schema_version", "arguments"}
                        )
                        or answer.get("stage") != stage
                    ):
                        raise ValueError("DSS acknowledgement binding differs")
                    if answer.get("outcome") in {
                        "MISSING",
                        "UNCERTAIN",
                        "INDETERMINATE",
                    }:
                        raise UncertainEffect("DSS reported uncertain command outcome")
                    admission.settle(stage, raw)
                    receipts.append(answer)
                    if answer.get("outcome") != expected:
                        return False, receipts
            return True, receipts
        except BaseException as error:
            if sent:
                try:
                    admission.uncertain(stage)
                except BaseException as persistence_error:
                    raise UncertainEffect(
                        "Effect ledger unavailable; authority must remain fenced"
                    ) from persistence_error
            if sent:
                raise UncertainEffect(
                    "DSS command may have taken effect; no automatic replay"
                ) from error
            raise
