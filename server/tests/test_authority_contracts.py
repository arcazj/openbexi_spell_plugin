import uuid

import pytest

from openbexi_spell_server.contracts import Fault, envelope, validate_envelope


def decision():
    return dict(
        execution_id=str(uuid.uuid4()),
        connection_id=str(uuid.uuid4()),
        claim_id=str(uuid.uuid4()),
        expected_epoch=1,
        connection_generation=1,
        capability="a" * 64,
        decision="accept",
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("execution_id", "forged"),
        ("connection_id", []),
        ("claim_id", None),
        ("expected_epoch", True),
        ("expected_epoch", -1),
        ("expected_epoch", 10**200),
        ("connection_generation", 0),
        ("connection_generation", False),
        ("capability", "not-a-token"),
        ("capability", "\u2603" * 64),
        ("decision", "force"),
        ("decision", {"accept": True}),
    ],
)
def test_strict_claim_proof_schema(field, value):
    body = {**decision(), field: value}
    with pytest.raises(Fault):
        validate_envelope(envelope("A", "alice", "execution.decide", body, "key"), "A")


def test_extra_owner_role_or_context_cannot_be_injected_into_reservation():
    body = dict(
        procedure_id="P",
        connection_id=str(uuid.uuid4()),
        source_revision="a" * 40,
        source_sha256="b" * 64,
        runtime_image="sha256:" + "c" * 64,
        driver_binding="driver",
    )
    for field in ("owner", "role", "context_id", "worker_slot", "authority_incarnation"):
        with pytest.raises(Fault, match="invalid_fields"):
            validate_envelope(
                envelope("A", "alice", "execution.reserve", {**body, field: "forged"}, "key"), "A"
            )
    for field, value in (
        ("source_revision", "branch"),
        ("source_sha256", "bad"),
        ("runtime_image", "image:latest"),
        ("driver_binding", "../driver"),
    ):
        with pytest.raises(Fault):
            validate_envelope(
                envelope("A", "alice", "execution.reserve", {**body, field: value}, "key"), "A"
            )


def test_private_worker_and_effect_methods_are_not_rpc_methods():
    for method in ("execution.start", "worker.consume_start", "driver.send", "execution.recover"):
        with pytest.raises(Fault, match="method_not_available"):
            validate_envelope(envelope("A", "alice", method, {}, "key"), "A")
