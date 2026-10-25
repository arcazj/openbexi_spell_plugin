"""Shared authority test operations, independent of the optional driver stack."""

import test_preflight as helpers


def accept(setup, *, key=None):
    bob = setup["controller"]("session.open", {}, subject="bob")["connection_id"]
    claim = setup["controller"](
        "execution.claim",
        dict(execution_id=setup["execution"]["id"], connection_id=bob, expected_epoch=1),
        subject="bob",
    )
    payload = dict(
        **helpers.proof(setup["execution"]), claim_id=claim["claim_id"], decision="accept"
    )
    decision = setup["controller"]("execution.decide", payload, key=key)
    return decision, payload
