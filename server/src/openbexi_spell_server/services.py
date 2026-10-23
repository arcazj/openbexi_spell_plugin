"""Context-local ACLs and fixed Listener routing. Execution APIs intentionally absent."""

from .contracts import (
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
    def __init__(self, store, listener_fingerprint, subjects):
        self.store = store
        self.listener_fingerprint = fingerprint(listener_fingerprint)
        self.subjects = policy(subjects)

    def authenticate(self, peer, headers):
        if peer != self.listener_fingerprint:
            raise Fault(403, "listener_identity_required")
        if headers.get_all("X-OpenBEXI-Client-Fingerprint"):
            raise Fault(403, "unexpected_client_identity")

    def handle(self, method, path, headers, body):
        if method != "POST" or path != "/v1/rpc":
            raise Fault(404, "route_not_available")
        request = validate_envelope(body, self.store.context_id)
        actor = self.subjects.get(request["subject"])
        if actor is None:
            raise Fault(403, "subject_denied")
        action = request["method"]
        # This always precedes replay lookup, including for an identical request.
        actor.require(METHODS[action])
        if action == "health":
            state = self.store.snapshot(values=False)
            result = {k: state[k] for k in ("context_id", "incarnation", "runtime_enabled")}
            result["status"] = "ready"
        elif action == "snapshot":
            result = self.store.snapshot(values=False)
        elif action == "blackboard.get":
            result = self.store.snapshot()
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

    def handle(self, method, path, headers, body):
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
        if method == "GET" and resource in ("health", "snapshot", "blackboard"):
            action = "blackboard.get" if resource == "blackboard" else resource
            payload = {}
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
