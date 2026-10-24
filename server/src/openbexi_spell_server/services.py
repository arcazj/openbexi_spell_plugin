"""Context-local ACLs, prelaunch authority and fixed Listener routing. No native launch."""

from dataclasses import asdict

from .authority import ExecutionAuthority
from .launch import WorkerLaunch
from .preflight import WorkerPeer, WorkerPreflight
from .snapshots import SnapshotCatalog
from .contracts import (
    AUTHORITY_MUTATIONS,
    METHODS,
    Fault,
    envelope,
    exact,
    fingerprint,
    identifier,
    policy,
    validate_envelope,
)


def one_header(headers, name):
    values = headers.get_all(name, [])
    if len(values) != 1:
        raise Fault(403, "identity_required")
    return values[0]


class Context:
    def __init__(
        self,
        store,
        listener_fingerprint,
        subjects,
        *,
        worker_slots=None,
        approved_sources=None,
        worker_credentials=None,
        worker_launch=None,
        native_driver_factory=None,
        native_pause=None,
        native_children=None,
        native_controls=None,
    ):
        self.store = store
        self.listener_fingerprint = fingerprint(listener_fingerprint)
        self.subjects = policy(subjects)
        self.catalog = SnapshotCatalog(approved_sources) if approved_sources is not None else None
        self.authority = ExecutionAuthority(store, self.subjects, worker_slots=worker_slots)
        self.preflight = None
        if self.catalog is not None:
            self.authority.reservation_validator = self.catalog.approve
        if worker_credentials is not None:
            if self.catalog is None:
                raise ValueError("Worker preflight requires approved source catalog")
            self.preflight = WorkerPreflight(
                self.authority, self.catalog, worker_credentials, self.listener_fingerprint
            )
        if worker_launch not in (None, "retained-single-use"):
            raise ValueError("Unsupported worker launch profile")
        if worker_launch is not None and self.preflight is None:
            raise ValueError("Worker launch requires source preflight and unique identities")
        if native_driver_factory is not None and worker_launch is None:
            raise ValueError("Native driver requires the explicit retained launch profile")
        self.native_driver = (
            native_driver_factory(self.authority) if native_driver_factory is not None else None
        )
        self.launch = (
            WorkerLaunch(self.preflight, self.native_driver) if worker_launch is not None else None
        )
        if native_pause not in (None, "fenced-probe"):
            raise ValueError("Unsupported native pause profile")
        if native_pause is not None:
            if self.launch is None:
                raise ValueError("Native pause requires the explicit retained launch profile")
            from .pause import NativePauseBarrier

            NativePauseBarrier(self.authority)
        if native_children not in (None, "admission-only"):
            raise ValueError("Unsupported native child profile")
        if native_children is not None:
            if self.launch is None:
                raise ValueError("Child admission requires the explicit retained launch profile")
            from .family import FamilyAdmission

            FamilyAdmission(self.authority, self.catalog)
        if native_controls not in (None, "run-journal"):
            raise ValueError("Unsupported native control profile")
        if native_controls is not None:
            if self.launch is None:
                raise ValueError("Native controls require the explicit retained launch profile")
            from .control import NativeControlJournal

            NativeControlJournal(self.authority)
        self.authority.start_guard = self._require_preflight

    def close(self):
        if self.native_driver is not None:
            self.native_driver.close()

    def _require_preflight(self, row):
        if self.preflight is None:
            raise Fault(403, "worker_preflight_required")
        self.preflight.require_ready(row)

    def authenticate(self, peer, headers):
        if headers.get_all("X-OpenBEXI-Client-Fingerprint"):
            raise Fault(403, "unexpected_client_identity")
        if self.preflight is not None and peer in self.preflight.peers:
            return self.preflight.peers[peer]
        if peer != self.listener_fingerprint:
            raise Fault(403, "listener_identity_required")
        return "listener"

    def handle(self, method, path, headers, body, *, identity=None):
        if isinstance(identity, WorkerPeer):
            if method != "POST" or self.preflight is None:
                raise Fault(404, "route_not_available")
            handler = (
                self.launch
                if path
                in (
                    "/v1/worker/consume",
                    "/v1/worker/check",
                    "/v1/worker/event",
                    "/v1/worker/driver",
                    "/v1/worker/pause-poll",
                    "/v1/worker/pause-report",
                    "/v1/worker/child-admit",
                    "/v1/worker/child-consume",
                    "/v1/worker/control-admit",
                    "/v1/worker/control-report",
                    "/v1/worker/control-forward",
                )
                else self.preflight
            )
            if handler is None:
                raise Fault(404, "route_not_available")
            return {
                "schema": "openbexi.worker/2" if handler is self.launch else "openbexi.worker/1",
                "result": handler.handle(identity, path, body),
            }
        if identity != "listener":
            raise Fault(403, "listener_identity_required")
        if method != "POST" or path != "/v1/rpc":
            raise Fault(404, "route_not_available")
        request = validate_envelope(
            body, self.store.context_id, allow_launch=self.launch is not None
        )
        actor = self.subjects.get(request["subject"])
        if actor is None:
            raise Fault(403, "subject_denied")
        action = request["method"]
        # This always precedes replay lookup, including for an identical request.
        actor.require("execution:start" if action == "execution.start" else METHODS[action])
        if action == "health":
            state = self.store.snapshot(values=False)
            result = {k: state[k] for k in ("context_id", "incarnation", "runtime_enabled")}
            result["status"] = "ready"
            result["subject"] = actor.subject
            result["permissions"] = sorted(actor.permissions)
        elif action == "snapshot":
            result = self.store.snapshot(values=False)
        elif action == "blackboard.get":
            result = self.store.snapshot()
        elif action == "source.catalog":
            if self.catalog is None:
                raise Fault(404, "source_catalog_unconfigured")
            result = self.catalog.metadata()
        elif action == "execution.list":
            result = self.authority.list_executions(actor.subject)
        elif action == "execution.start":
            # Explicit retained profile only; the normal Listener/gateway still
            # cannot route this operator-to-Context admission. Token delivery is
            # one-shot; a lost response never replays a plaintext grant.
            result = {
                "grant": asdict(self.authority.admit_start(actor.subject, request["payload"])),
                "hold_retained": True,
                "runtime_enabled": False,
            }
        elif action in AUTHORITY_MUTATIONS:
            result = self.authority.mutate(
                actor.subject, action, request["idempotency_key"], request["payload"]
            )
        else:
            result = self.store.cas(actor.subject, request["idempotency_key"], request["payload"])
        return {"schema": "openbexi.context/1", "result": result}


class Listener:
    def __init__(self, edge_fingerprint, identities, scopes, contexts):
        self.edge_fingerprint = fingerprint(edge_fingerprint)
        self.identities = {
            fingerprint(cert): identifier(subject) for cert, subject in identities.items()
        }
        self.contexts = {identifier(name): route for name, route in contexts.items()}
        self.scopes = {
            identifier(subject): frozenset(identifier(c) for c in names)
            for subject, names in scopes.items()
        }
        if any(c not in self.contexts for names in self.scopes.values() for c in names):
            raise ValueError("Subject scope references an unconfigured Context")

    def authenticate(self, peer, headers):
        if peer != self.edge_fingerprint:
            raise Fault(403, "edge_identity_required")
        client = fingerprint(one_header(headers, "X-OpenBEXI-Client-Fingerprint"))
        if client not in self.identities:
            raise Fault(403, "user_identity_denied")

    def handle(self, method, path, headers, body, *, identity=None):
        subject = self.identities[one_header(headers, "X-OpenBEXI-Client-Fingerprint")]
        allowed = self.scopes.get(subject, frozenset())
        if method == "GET" and path == "/v1/health":
            return dict(schema="openbexi.listener/1", status="ready", runtime_enabled=False)
        if method == "GET" and path == "/v1/contexts":
            return dict(
                schema="openbexi.listener/1",
                contexts=sorted(allowed),
                registry="configured",
                runtime_enabled=False,
            )
        parts = path.split("/")
        if len(parts) != 5 or parts[1:3] != ["v1", "contexts"]:
            raise Fault(404, "route_not_available")
        context_id, resource = parts[3:]
        if context_id not in allowed:
            raise Fault(403, "context_scope_denied")
        key = None
        payload: dict
        if method == "GET" and resource in ("health", "snapshot", "blackboard"):
            action = "blackboard.get" if resource == "blackboard" else resource
            payload = {}
        elif method == "GET" and resource == "procedures":
            action, payload = "source.catalog", {}
        elif method == "GET" and resource == "executions":
            action, payload = "execution.list", {}
        elif method == "POST" and resource == "authority":
            exact(body, {"method", "payload"})
            if not isinstance(body["method"], str) or body["method"] not in AUTHORITY_MUTATIONS:
                raise Fault(404, "method_not_available")
            action, payload = body["method"], body["payload"]
            key = identifier(one_header(headers, "Idempotency-Key"))
        elif method == "POST" and resource == "blackboard":
            exact(body, {"key", "expected_revision", "value"})
            payload, action = body, "blackboard.cas"
            key = identifier(one_header(headers, "Idempotency-Key"))
        else:
            raise Fault(404, "route_not_available")
        request = envelope(context_id, subject, action, payload, key)
        validate_envelope(request, context_id)
        result = self.contexts[context_id].call(request)
        return {"schema": "openbexi.listener/1", "result": result}
