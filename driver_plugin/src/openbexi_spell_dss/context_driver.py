"""Context-owned original TC/TM subset with mandatory actual-send admission.

The worker supplies only original protobuf bytes, its immutable start grant and
one request UUID. Endpoints, resource permissions, operation identity and wire
execution identity are derived here, never taken from the worker payload.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import threading
import time
from urllib.parse import urlsplit

from google.protobuf import message_factory
from google.protobuf.wrappers_pb2 import BoolValue

from openbexi_spell_server.contracts import Fault, exact, identifier
from openbexi_spell_server.effects import DriverGate, EffectAdmission, provenance
from openbexi_spell_server.preflight import canonical_uuid

from .codec import pack, unpack
from .fenced_transport import CommandTiming, Transport
from .rpc import config as modifiers, method_descriptor
from .stubs import SPELLDriver_pb2 as proto


PREFIX = "/spell.driver.SPELLDriverInterface_"
METHODS = frozenset(
    PREFIX + suffix
    for suffix in (
        "TC/CreateTcItem",
        "TC/SendCommand",
        "TM/CreateTmItem",
        "TM/DatabaseLookup",
        "TM/RefreshItem",
    )
)
MAX_INFLIGHT_COMMANDS = 10


def failure_chain(error):
    """Bounded type/code diagnostics only; exception messages can contain secrets."""
    result, seen = [], set()
    while error is not None and id(error) not in seen and len(result) < 8:
        seen.add(id(error))
        item = dict(type=type(error).__name__[:80])
        if isinstance(error, Fault):
            item["code"] = error.code
        timing = getattr(error, "_dss_command_timing", None)
        if type(timing) is CommandTiming:
            item["command_timing"] = timing.snapshot()
        result.append(item)
        error = error.__cause__ or error.__context__
    return result


class ContextDriver:
    """One fixed simulator binding per Context; no reset/global mutations/replay."""

    def __init__(self, authority, settings):
        exact(settings, {"binding", "url", "tcp", "directory", "commands", "telemetry"})
        binding = identifier(settings["binding"])
        if binding == "context-audit":
            raise ValueError("DSS binding cannot replace the audit-only profile")
        endpoint = settings["tcp"]
        if type(endpoint) is not list or len(endpoint) != 2:
            raise ValueError("DSS TCP endpoint must be a fixed IPv4 address and port")
        ipaddress.IPv4Address(endpoint[0])
        if type(endpoint[1]) is not int or not 1 <= endpoint[1] <= 65535:
            raise ValueError("Invalid DSS port")
        url = urlsplit(settings["url"])
        if (
            url.scheme != "http"
            or url.hostname != endpoint[0]
            or url.username is not None
            or url.password is not None
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or url.port is None
        ):
            raise ValueError("DSS metadata must use the fixed service-owned IPv4 host")
        self.commands = self._resources(settings["commands"], 32)
        self.telemetry = self._resources(settings["telemetry"], 128)
        if not self.commands and not self.telemetry:
            raise ValueError("At least one explicit resource permission is required")
        self.authority, self.store = authority, authority.store
        self.binding, self.bindings = binding, frozenset({binding})
        # This fixed simulator supports independent per-operation TCP streams.
        # Bound them to the ten-worker profile (below DSS's 16 TCP handlers),
        # without serializing receipt waits across unrelated operations.
        # The actual-send execution mutex remains the authorization boundary.
        self.command_slots = threading.BoundedSemaphore(MAX_INFLIGHT_COMMANDS)
        self.transport = self.gate = None
        try:
            self.transport = Transport(settings["url"], endpoint)
            for command in self.commands:
                if self.transport.database.command(command)["critical"]:
                    raise ValueError("Critical command confirmation is not qualified")
            for item in self.telemetry:
                self.transport.database.item(item)
            self.gate = DriverGate(
                authority, settings["directory"], {binding: tuple(endpoint)}
            )
            with self.store.transaction():
                self.store.db.execute(
                    "CREATE TABLE IF NOT EXISTS native_driver_calls("
                    "request_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,"
                    "provenance TEXT NOT NULL,binding TEXT NOT NULL,path TEXT NOT NULL,"
                    "payload_hash TEXT NOT NULL,state TEXT NOT NULL,response_hash TEXT)"
                )
                self.store.db.execute(
                    "UPDATE native_driver_calls SET state='UNCERTAIN' WHERE state='ADMITTED'"
                )
                if self.store.db.execute("PRAGMA user_version").fetchone()[0] < 7:
                    self.store.db.execute("PRAGMA user_version=7")
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _resources(value, maximum):
        if (
            type(value) is not list
            or len(value) > maximum
            or any(type(name) is not str or not 1 <= len(name) <= 128 for name in value)
            or len(set(value)) != len(value)
        ):
            raise ValueError("Explicit bounded, unique resource permissions required")
        return frozenset(value)

    def _live(self, grant):
        row = self.authority._grant(grant)
        if (
            row["lifecycle"] != "STARTING"
            or json.loads(row["inventory"])["driver_binding"] != self.binding
        ):
            raise Fault(403, "native_driver_binding_denied")
        return row

    def _resource(self, name, *, command=False):
        if name not in (self.commands if command else self.telemetry):
            raise Fault(403, "native_driver_resource_denied")
        return (
            self.transport.database.command(name)
            if command
            else self.transport.database.item(name)
        )

    def dispatch(self, grant, request_id, path, raw):
        canonical_uuid(request_id)
        if path not in METHODS or type(raw) is not bytes or len(raw) > 32768:
            raise Fault(403, "native_driver_method_denied")
        with self.store.transaction(write=False):
            row = self._live(grant)
            identity = {
                "definition": row["procedure_id"],
                "procedure": grant.execution_id,
            }
        method = method_descriptor(path)
        try:
            message = message_factory.GetMessageClass(method.input_type).FromString(raw)
            action = self._prepare(grant, request_id, path, message, identity)
        except Fault:
            raise
        except Exception as error:
            raise Fault(400, "native_driver_request_invalid") from error
        # All calls, including reads, have one non-replayable durable identity.
        # No plaintext grant or protobuf response is stored in this ledger.
        with self.store.transaction():
            self._live(grant)
            if self.store.db.execute(
                "SELECT 1 FROM native_driver_calls WHERE request_id=?",
                (request_id,),
            ).fetchone():
                raise Fault(409, "native_driver_replay_denied")
            if (
                self.store.db.execute(
                    "SELECT COUNT(*) FROM native_driver_calls"
                ).fetchone()[0]
                >= 512
            ):
                raise Fault(503, "native_driver_capacity_reached")
            self.store.db.execute(
                "INSERT INTO native_driver_calls VALUES(?,?,?,?,?,?,'ADMITTED',NULL)",
                (
                    request_id,
                    grant.execution_id,
                    provenance(grant),
                    self.binding,
                    path,
                    hashlib.sha256(raw).hexdigest(),
                ),
            )
        try:
            result = action()
            if result.DESCRIPTOR.full_name != method.output_type.full_name:
                raise RuntimeError("Original driver response type differs")
            response = result.SerializeToString(deterministic=True)
            if len(response) > 32768:
                raise RuntimeError("Original driver response exceeds bounds")
            with self.store.transaction():
                self._live(grant)  # No post-revocation result disclosure.
                self.store.db.execute(
                    "UPDATE native_driver_calls SET state='COMPLETED',response_hash=? "
                    "WHERE request_id=?",
                    (hashlib.sha256(response).hexdigest(), request_id),
                )
            return response
        except BaseException as error:
            # Command-stage uncertainty is already fenced by DriverGate. Keep
            # the original call as uncertain as well; no replay/recovery grant.
            with self.store.transaction():
                self.store.db.execute(
                    "UPDATE native_driver_calls SET state='UNCERTAIN' WHERE request_id=?",
                    (request_id,),
                )
                self.store._event(
                    "NATIVE_DRIVER_CALL_FAILED",
                    dict(
                        execution_id=grant.execution_id,
                        request_id=request_id,
                        path=path,
                        error_type=type(error).__name__,
                        error_chain=failure_chain(error),
                        error_code=error.code
                        if isinstance(error, Fault)
                        else "driver_operation_failed",
                    ),
                )
            raise

    def _prepare(self, grant, request_id, path, request, identity):
        name = path.rsplit("/", 1)[1]
        command = path.startswith(PREFIX + "TC/")
        if name in {"CreateTcItem", "CreateTmItem"}:
            item = self._resource(request.mnemonic, command=command)
            if command:
                return lambda: proto.TcItemDesc(
                    mnemonic=item["name"],
                    description=item["effect"],
                    id=str(item["command_code"]),
                )
            return lambda: proto.TmItemDesc(
                mnemonic=item["item_id"],
                description=item.get("description", item["item_id"]),
                id=str(item["item_code"]),
            )
        if name == "DatabaseLookup":
            if request.source not in {"", "GENERIC"} or request.type not in {
                "TC",
                "TM",
            }:
                raise ValueError("Unsupported database source/type")
            item = self._resource(request.name, command=request.type == "TC")
            if request.type == "TC":
                # The installed native proxy's critical-command check requires
                # the original catalog discriminator, even for plain commands.
                # Resource admission above still denies sequences/unknown TCs.
                item = dict(item, kind="COMMAND")
            return lambda: proto.LookupAnswer(lookup=pack(item))
        if name == "SendCommand":
            self._resource(request.command.mnemonic, command=True)
            settings = modifiers(request.config)
            timeout = settings.get("Timeout", 3)
            if (
                set(settings)
                - {"Timeout", "ConfirmCritical", "LoadOnly", "SendDelay", "addInfo"}
                or any(
                    key in settings
                    and (type(settings[key]) is not bool or settings[key])
                    for key in ("ConfirmCritical", "LoadOnly")
                )
                or (
                    "SendDelay" in settings
                    and (
                        type(settings["SendDelay"]) not in {int, float}
                        or settings["SendDelay"] != 0
                    )
                )
                or (
                    "addInfo" in settings
                    and (type(settings["addInfo"]) is not dict or settings["addInfo"])
                )
                or type(timeout) not in {int, float}
                or not math.isfinite(timeout)
                or not 0 < timeout <= 3
            ):
                raise ValueError(
                    "Only bounded timeout and neutral native command options are supported"
                )
            arguments = unpack(request.args) if request.args.type_url else []
            self.transport.arguments(request.command.mnemonic, arguments)
            bound = EffectAdmission(
                self.gate,
                grant,
                self.binding,
                request_id,
                deadline=time.monotonic() + timeout,
            )

            def send():
                if not self.command_slots.acquire(blocking=False):
                    raise Fault(503, "native_driver_resource_busy")
                try:
                    success, _ = self.transport.command(
                        request.command.mnemonic,
                        arguments,
                        identity,
                        request_id,
                        lambda: self.authority.validate_start_grant(grant),
                        admission=bound,
                        timeout=timeout,
                    )
                    return BoolValue(value=success)
                finally:
                    self.command_slots.release()

            return send
        self._resource(request.item.mnemonic)
        settings = modifiers(request.config)
        wait, timeout = settings.get("Wait", False), settings.get("Timeout", 3)
        if (
            set(settings) - {"Wait", "Timeout", "ValueFormat"}
            or type(wait) is not bool
            or type(timeout) not in {int, float}
            or not math.isfinite(timeout)
            or not 0 < timeout <= 3
            or settings.get("ValueFormat", "Eng format")
            not in {"Raw format", "Eng format", "Default format"}
        ):
            raise ValueError("Unsupported telemetry refresh modifiers")

        def refresh():
            self.authority.validate_start_grant(grant)
            state = self.transport.current_state()
            if (
                state["epoch"] != self.transport.epoch
                or state["scenario_id"] != self.transport.scenario
            ):
                raise ValueError("DSS epoch changed; explicit rebinding required")
            sample = self.transport.sample(
                request.item.mnemonic, wait=wait, timeout=timeout
            )
            stamp = datetime.fromtimestamp(
                sample["acquired_at_unix_ns"] / 1e9, timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S.%f")
            return proto.TmItemValue(
                item=request.item,
                validity=sample["validity"] == "VALID"
                and sample["quality"] == "GOOD"
                and -1 <= (time.time_ns() - sample["acquired_at_unix_ns"]) / 1e9 <= 5
                and sample["synchronization_state"] == "COMPLETE",
                engValue=pack(sample["engineering"]["value"]),
                rawValue=pack(sample["raw"]["value"]),
                timestamp=stamp,
                config=request.config,
            )

        return refresh

    def close(self):
        if self.transport is not None:
            self.transport.close()
        if self.gate is not None:
            self.gate.close()
