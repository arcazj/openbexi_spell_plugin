"""Opt-in retained single-use worker launch RPC, never a controller start route."""

from dataclasses import fields

from .authority import StartGrant
from .contracts import Fault, exact, fingerprint, identifier
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

    def handle(self, peer, path, body):
        if self.preflight.peers.get(peer.fingerprint) != peer:
            raise Fault(403, "worker_identity_required")
        if path not in ("/v1/worker/consume", "/v1/worker/check"):
            raise Fault(404, "route_not_available")
        exact(body, {"schema", "context_id", "grant"})
        if (
            body["schema"] != "openbexi.worker/1"
            or body["context_id"] != self.authority.store.context_id
        ):
            raise Fault(403, "worker_scope_denied")
        grant = start_grant(body["grant"])
        if grant.worker_slot != peer.slot or grant.worker_incarnation != peer.incarnation:
            raise Fault(403, "worker_assignment_mismatch")
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
