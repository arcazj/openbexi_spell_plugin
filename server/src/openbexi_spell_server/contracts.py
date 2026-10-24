"""Bounded wire contracts. No request body can assign its caller's permissions."""

import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import dataclass

MAX_BODY = 65536
MAX_DEPTH = 16
PERMISSIONS = frozenset(
    {
        "context:read",
        "blackboard:read",
        "blackboard:admin",
        "execution:read",
        "execution:start",
        "execution:control",
        "execution:request_control",
    }
)
METHODS = {
    "health": "context:read",
    "snapshot": "context:read",
    "blackboard.get": "blackboard:read",
    "blackboard.cas": "blackboard:admin",
    "session.open": "execution:control",
    "session.close": "execution:control",
    "execution.list": "execution:read",
    "source.catalog": "execution:read",
    "execution.reserve": "execution:start",
    "execution.rebind": "execution:control",
    "execution.claim": "execution:request_control",
    "execution.decide": "execution:control",
    "execution.cancel": "execution:request_control",
}


class Fault(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def identifier(value, *, maximum=128):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", value):
        raise Fault(400, "invalid_identifier")
    if len(value) > maximum:
        raise Fault(400, "invalid_identifier")
    return value


def fingerprint(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise Fault(400, "invalid_certificate_identity")
    return value


def canonical(value) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")
    except (ValueError, TypeError, RecursionError) as error:
        raise Fault(400, "invalid_json") from error


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def decode(raw: bytes):
    if len(raw) > MAX_BODY:
        raise Fault(413, "body_too_large")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
        )
        pending = [(value, 1)]
        while pending:
            item, depth = pending.pop()
            if depth > MAX_DEPTH:
                raise ValueError("json_too_deep")
            if isinstance(item, dict):
                pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError("nonfinite_json")
        return value
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Fault(400, "invalid_json") from error


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise Fault(400, "invalid_fields")
    return value


@dataclass(frozen=True)
class Actor:
    subject: str
    permissions: frozenset[str]

    def require(self, permission):
        if permission not in self.permissions:
            raise Fault(403, "permission_denied")


def policy(value):
    if type(value) is not dict or len(value) > 128:
        raise ValueError("Invalid subject policy")
    result = {}
    for subject, permissions in value.items():
        identifier(subject)
        if type(permissions) is not list or any(p not in PERMISSIONS for p in permissions):
            raise ValueError("Invalid permissions")
        result[subject] = Actor(subject, frozenset(permissions))
    return result


def envelope(context, subject, method, payload, key=None):
    now = time.time()
    return dict(
        schema="openbexi.context/1",
        request_id=str(uuid.uuid4()),
        context_id=context,
        subject=subject,
        issued_at=now,
        deadline=now + 5,
        method=method,
        payload=payload,
        payload_sha256=digest(payload),
        idempotency_key=key,
    )


def validate_envelope(value, context, *, now=None, allow_launch=False):
    exact(
        value,
        {
            "schema",
            "request_id",
            "context_id",
            "subject",
            "issued_at",
            "deadline",
            "method",
            "payload",
            "payload_sha256",
            "idempotency_key",
        },
    )
    if value["schema"] != "openbexi.context/1" or value["context_id"] != context:
        raise Fault(403, "delegation_scope_denied")
    try:
        if str(uuid.UUID(value["request_id"])) != value["request_id"]:
            raise ValueError("noncanonical_uuid")
    except (ValueError, TypeError, AttributeError) as error:
        raise Fault(400, "invalid_request_id") from error
    identifier(value["subject"])
    now = time.time() if now is None else now
    issued, deadline = value["issued_at"], value["deadline"]
    if (
        type(issued) not in (float, int)
        or type(deadline) not in (float, int)
        or abs(issued) > 10**12
        or abs(deadline) > 10**12
        or not math.isfinite(issued)
        or not math.isfinite(deadline)
        or issued > now + 1
        or deadline <= now
        or not 0 < deadline - issued <= 5.001
        or issued < now - 6
    ):
        raise Fault(403, "delegation_expired")
    method = value["method"]
    if not isinstance(method, str) or (
        method not in METHODS and not (allow_launch and method == "execution.start")
    ):
        raise Fault(404, "method_not_available")
    if value["payload_sha256"] != digest(value["payload"]):
        raise Fault(400, "payload_digest_mismatch")
    if method == "blackboard.cas":
        identifier(value["idempotency_key"])
        body = exact(value["payload"], {"key", "expected_revision", "value"})
        identifier(body["key"])
        if type(body["expected_revision"]) is not int or body["expected_revision"] < 0:
            raise Fault(400, "invalid_revision")
        if len(canonical(body["value"])) > 16384:
            raise Fault(413, "value_too_large")
    elif method in AUTHORITY_MUTATIONS or (allow_launch and method == "execution.start"):
        identifier(value["idempotency_key"])
        validate_authority_payload(method, value["payload"])
    else:
        exact(value["payload"], set())
        if value["idempotency_key"] is not None:
            raise Fault(400, "unexpected_idempotency_key")
    return value


AUTHORITY_MUTATIONS = frozenset(
    {
        "session.open",
        "session.close",
        "execution.reserve",
        "execution.rebind",
        "execution.claim",
        "execution.decide",
        "execution.cancel",
    }
)
AUTHORITY_FIELDS = {
    # Deliberately absent from METHODS/AUTHORITY_MUTATIONS: trusted adapter only.
    "execution.start": {
        "execution_id",
        "connection_id",
        "expected_epoch",
        "connection_generation",
        "capability",
    },
    "session.open": set(),
    "session.close": {"connection_id"},
    "execution.reserve": {
        "procedure_id",
        "connection_id",
        "source_revision",
        "source_sha256",
        "runtime_image",
        "driver_binding",
    },
    "execution.rebind": {"execution_id", "connection_id", "expected_epoch"},
    "execution.claim": {"execution_id", "connection_id", "expected_epoch"},
    "execution.decide": {
        "execution_id",
        "connection_id",
        "expected_epoch",
        "connection_generation",
        "capability",
        "claim_id",
        "decision",
    },
    "execution.cancel": {"execution_id", "connection_id", "claim_id"},
}


def validate_authority_payload(method, body):
    exact(body, AUTHORITY_FIELDS[method])
    for key in ("execution_id", "connection_id", "claim_id"):
        if key in body:
            try:
                if str(uuid.UUID(body[key])) != body[key]:
                    raise ValueError("noncanonical_uuid")
            except (ValueError, TypeError, AttributeError) as error:
                raise Fault(400, "invalid_authority_id") from error
    for key in ("expected_epoch", "connection_generation"):
        if key in body and (type(body[key]) is not int or not 1 <= body[key] < 2**63 - 1):
            raise Fault(400, "invalid_authority_generation")
    if "capability" in body:
        fingerprint(body["capability"])
    if "decision" in body and body["decision"] not in ("accept", "reject"):
        raise Fault(400, "invalid_claim_decision")
    if method == "execution.reserve":
        identifier(body["procedure_id"])
        identifier(body["driver_binding"])
        fingerprint(body["source_sha256"])
        if not isinstance(body["source_revision"], str) or not re.fullmatch(
            "[0-9a-f]{40}", body["source_revision"]
        ):
            raise Fault(400, "invalid_source_revision")
        if not isinstance(body["runtime_image"], str) or not re.fullmatch(
            "sha256:[0-9a-f]{64}", body["runtime_image"]
        ):
            raise Fault(400, "invalid_runtime_image")
    return body
