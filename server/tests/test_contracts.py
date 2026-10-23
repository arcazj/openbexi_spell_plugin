import time

import pytest

from openbexi_spell_server.contracts import Fault, decode, envelope, validate_envelope


@pytest.mark.parametrize(
    "raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"\xff", b"[" * 20 + b"0" + b"]" * 20]
)
def test_invalid_json_is_rejected(raw):
    with pytest.raises(Fault) as caught:
        decode(raw)
    assert caught.value.status == 400


@pytest.mark.parametrize(
    "change,status",
    [
        ({"schema": "other/1"}, 403),
        ({"context_id": "B"}, 403),
        ({"request_id": "fake"}, 400),
        ({"issued_at": True}, 403),
        ({"issued_at": 10**500}, 403),
        ({"deadline": 10**500}, 403),
        ({"deadline": time.time() - 10}, 403),
        ({"payload_sha256": "wrong"}, 400),
        ({"role": "admin"}, 400),
        ({"method": "execution.start"}, 404),
        ({"idempotency_key": "unexpected"}, 400),
    ],
)
def test_delegation_rejects_scope_expiry_forgery_and_unknown_fields(change, status):
    value = envelope("A", "alice", "health", {})
    value.update(change)
    with pytest.raises(Fault) as caught:
        validate_envelope(value, "A")
    assert caught.value.status == status


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "ok", "expected_revision": True, "value": 1},
        {"key": "../escape", "expected_revision": 0, "value": 1},
        {"key": "ok", "expected_revision": -1, "value": 1},
        {"key": "ok", "expected_revision": 0, "value": "x" * 17000},
    ],
)
def test_invalid_blackboard_contract(payload):
    value = envelope("A", "alice", "blackboard.cas", payload, "key-1")
    with pytest.raises(Fault):
        validate_envelope(value, "A")
