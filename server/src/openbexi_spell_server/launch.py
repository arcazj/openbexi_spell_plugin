"""Opt-in retained single-use worker launch RPC, never a controller start route."""

from dataclasses import fields
import json

from .authority import StartGrant
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
    def __init__(self, preflight):
        self.preflight = preflight
        self.authority = preflight.authority
        with self.authority.store.transaction():
            self.authority.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_driver_events(request_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,body_hash TEXT NOT NULL)"
            )
            if self.authority.store.db.execute("PRAGMA user_version").fetchone()[0] < 6:
                self.authority.store.db.execute("PRAGMA user_version=6")

    def handle(self, peer, path, body):
        if self.preflight.peers.get(peer.fingerprint) != peer:
            raise Fault(403, "worker_identity_required")
        if path not in ("/v1/worker/consume", "/v1/worker/check", "/v1/worker/event"):
            raise Fault(404, "route_not_available")
        exact(
            body,
            {"schema", "context_id", "grant"}
            | ({"request_id", "message", "severity", "scope"} if path.endswith("event") else set()),
        )
        if (
            body["schema"] != "openbexi.worker/1"
            or body["context_id"] != self.authority.store.context_id
        ):
            raise Fault(403, "worker_scope_denied")
        grant = start_grant(body["grant"])
        if grant.worker_slot != peer.slot or grant.worker_incarnation != peer.incarnation:
            raise Fault(403, "worker_assignment_mismatch")
        if path.endswith("event"):
            return self.record_event(grant, body)
        if path.endswith("consume"):
            self.authority.consume_start(grant, peer.slot, peer.incarnation)
        else:
            self.authority.validate_start_grant(grant)
        # No grant token, capability, new epoch or retry permission is returned.
        return dict(
            consumed=path.endswith("consume"),
            checked=path.endswith("check"),
            execution_id=grant.execution_id,
            request_id=grant.request_id,
            authority_incarnation=grant.authority_incarnation,
            hold_retained=True,
            runtime_enabled=False,
        )

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
                if (
                    row["lifecycle"] != "STARTING"
                    or json.loads(row["inventory"])["driver_binding"] != "context-audit"
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
