"""Opt-in retained single-use worker launch RPC, never a controller start route."""

from dataclasses import fields
import base64
import binascii
import json
import hmac
import secrets

from .authority import StartGrant, secret_hash
from .contracts import Fault, digest, exact, fingerprint, identifier
from .preflight import canonical_uuid


def start_grant(value):
    exact(value, {field.name for field in fields(StartGrant)})
    for key in ("authority_incarnation", "execution_id", "connection_id", "request_id"):
        canonical_uuid(value[key])
    for key in ("worker_slot", "worker_incarnation"):
        identifier(value[key])
    for key in ("worker_generation", "control_epoch", "connection_generation"):
        if type(value[key]) is not int or not 1 <= value[key] <= 2**31 - 1:
            raise Fault(400, "invalid_start_grant")
    for key in ("operation_digest", "token"):
        fingerprint(value[key])
    return StartGrant(**value)


class WorkerLaunch:
    def __init__(self, preflight, driver=None):
        self.preflight = preflight
        self.authority = preflight.authority
        self.driver = driver
        with self.authority.store.transaction():
            self.authority.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_driver_events(request_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,body_hash TEXT NOT NULL)"
            )
            self.authority.store.db.execute(
                "CREATE TABLE IF NOT EXISTS worker_runtime_receipts("
                "execution_id TEXT PRIMARY KEY,request_id TEXT NOT NULL,capability_hash TEXT NOT NULL)"
            )
            if self.authority.store.db.execute("PRAGMA user_version").fetchone()[0] < 8:
                self.authority.store.db.execute("PRAGMA user_version=8")

    def handle(self, peer, path, body):
        if self.preflight.peers.get(peer.fingerprint) != peer:
            raise Fault(403, "worker_identity_required")
        allowed = {"/v1/worker/consume", "/v1/worker/check", "/v1/worker/event"}
        if self.driver is not None:
            allowed.add("/v1/worker/driver")
        pause = self.authority.native_pause
        safety_only = pause is not None and path in {
            "/v1/worker/pause-poll",
            "/v1/worker/pause-report",
        }
        if pause is not None:
            allowed.update({"/v1/worker/pause-poll", "/v1/worker/pause-report"})
        if path not in allowed:
            raise Fault(404, "route_not_available")
        if not path.endswith("consume"):
            if type(body) is not dict or "runtime_capability" not in body:
                raise Fault(403, "worker_consumption_proof_required")
        extra = set()
        if path.endswith("event"):
            extra = {"request_id", "message", "severity", "scope"}
        elif path.endswith("driver"):
            extra = {"request_id", "path", "payload"}
        elif path.endswith("pause-report"):
            extra = {"barrier_id", "provider", "native_status", "quiescence_proven", "reason"}
        if not path.endswith("consume"):
            extra.add("runtime_capability")
        exact(
            body,
            {"schema", "context_id", "grant"} | extra,
        )
        if (
            body["schema"] != "openbexi.worker/2"
            or body["context_id"] != self.authority.store.context_id
        ):
            raise Fault(403, "worker_scope_denied")
        grant = start_grant(body["grant"])
        if grant.worker_slot != peer.slot or grant.worker_incarnation != peer.incarnation:
            raise Fault(403, "worker_assignment_mismatch")
        if not path.endswith("consume"):
            self._runtime(grant, body["runtime_capability"], safety_only=safety_only)
        if path.endswith("pause-poll"):
            return pause.poll(grant)
        if path.endswith("pause-report"):
            return pause.report(grant, body)
        if path.endswith("event"):
            return self.record_event(grant, body)
        if path.endswith("driver"):
            canonical_uuid(body["request_id"])
            if (
                type(body["path"]) is not str
                or not 1 <= len(body["path"]) <= 256
                or type(body["payload"]) is not str
                or len(body["payload"]) > 43692
            ):
                raise Fault(400, "native_driver_request_invalid")
            try:
                raw = base64.b64decode(body["payload"], validate=True)
            except (ValueError, binascii.Error) as error:
                raise Fault(400, "native_driver_request_invalid") from error
            if len(raw) > 32768:
                raise Fault(413, "native_driver_request_too_large")
            self.authority.validate_start_grant(grant)
            result = self.driver.dispatch(grant, body["request_id"], body["path"], raw)
            if type(result) is not bytes or len(result) > 32768:
                raise Fault(503, "native_driver_response_invalid")
            return dict(
                request_id=body["request_id"],
                execution_id=grant.execution_id,
                payload=base64.b64encode(result).decode("ascii"),
            )
        if path.endswith("consume"):
            capability = secrets.token_hex(32)
            self.authority.consume_start(
                grant, peer.slot, peer.incarnation, consumption_hash=secret_hash(capability)
            )
        # Only the single consume winner receives a new memory-only runtime
        # proof. No original grant, new epoch or retry permission is returned.
        answer = dict(
            consumed=path.endswith("consume"),
            checked=path.endswith("check"),
            execution_id=grant.execution_id,
            request_id=grant.request_id,
            authority_incarnation=grant.authority_incarnation,
            hold_retained=True,
            runtime_enabled=False,
        )
        if path.endswith("consume"):
            answer["runtime_capability"] = capability
        return answer

    def _runtime(self, grant, capability, *, safety_only=False):
        try:
            fingerprint(capability)
        except Fault as error:
            raise Fault(403, "worker_consumption_proof_required") from error
        with self.authority._execution_lock(grant.execution_id):
            with self.authority.store.transaction(write=False):
                row = (
                    self.authority._original_grant(grant)
                    if safety_only
                    else self.authority._grant(grant)
                )
                receipt = self.authority.store.db.execute(
                    "SELECT request_id,capability_hash FROM worker_runtime_receipts WHERE execution_id=?",
                    (grant.execution_id,),
                ).fetchone()
                if (
                    row["lifecycle"] != "STARTING"
                    or receipt is None
                    or receipt["request_id"] != grant.request_id
                    or not hmac.compare_digest(receipt["capability_hash"], secret_hash(capability))
                ):
                    raise Fault(403, "worker_consumption_proof_required")

    def record_event(self, grant, body):
        canonical_uuid(body["request_id"])
        if (
            type(body["message"]) is not str
            or not 1 <= len(body["message"].encode("utf-8")) <= 8192
            or type(body["severity"]) is not int
            or body["severity"] not in {1, 2, 4, 8}
            or type(body["scope"]) is not int
            or body["scope"] != 1
        ):
            raise Fault(400, "native_event_denied")
        authority, store = self.authority, self.authority.store
        with authority._execution_lock(grant.execution_id):
            with store.transaction():
                row = authority._grant(grant)
                bindings = {"context-audit"}
                if self.driver is not None:
                    bindings.update(self.driver.bindings)
                if (
                    row["lifecycle"] != "STARTING"
                    or json.loads(row["inventory"])["driver_binding"] not in bindings
                ):
                    raise Fault(403, "native_event_denied")
                hashed = digest(body)
                previous = store.db.execute(
                    "SELECT execution_id,body_hash FROM native_driver_events WHERE request_id=?",
                    (body["request_id"],),
                ).fetchone()
                if previous:
                    if (
                        previous["execution_id"] != grant.execution_id
                        or previous["body_hash"] != hashed
                    ):
                        raise Fault(409, "native_event_conflict")
                else:
                    if (
                        store.db.execute("SELECT COUNT(*) FROM native_driver_events").fetchone()[0]
                        >= 8192
                        or store.db.execute(
                            "SELECT COUNT(*) FROM native_driver_events WHERE execution_id=?",
                            (grant.execution_id,),
                        ).fetchone()[0]
                        >= 512
                    ):
                        raise Fault(503, "native_event_capacity_reached")
                    store.db.execute(
                        "INSERT INTO native_driver_events VALUES(?,?,?)",
                        (body["request_id"], grant.execution_id, hashed),
                    )
                    store._event(
                        "NATIVE_DRIVER_EVENT",
                        dict(
                            execution_id=grant.execution_id,
                            request_id=body["request_id"],
                            control_epoch=grant.control_epoch,
                            worker_incarnation=grant.worker_incarnation,
                            message=body["message"],
                            severity=body["severity"],
                            scope=body["scope"],
                        ),
                    )
        return dict(recorded=True, request_id=body["request_id"], execution_id=grant.execution_id)
