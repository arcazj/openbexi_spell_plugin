"""Original protobuf over real worker mTLS to a separate DSS process.

This qualifies the Context RPC/effect boundary, not the native Executor,
cooperative quiescence, production deployment or the complete legacy driver.
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import uuid
import time

import pytest
from google.protobuf.wrappers_pb2 import BoolValue

from openbexi_spell_server.contracts import Fault, policy
from openbexi_spell_server.launch import WorkerLaunch
from openbexi_spell_server.services import Context
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.transport import Route
from test_effects import dss as dss_process_fixture
from test_launch import call, event_body, grant
import test_preflight as helpers
from test_services import request

from openbexi_spell_dss.context_driver import ContextDriver, METHODS, PREFIX
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as proto


@pytest.fixture
def independent_dss(tmp_path):
    yield from dss_process_fixture.__wrapped__(tmp_path)


@pytest.fixture
def driver_setup(tmp_path, pki, source, independent_dss):
    dss = independent_dss
    source["config"]["procedure"]["driver_binding"] = "simulator"
    for setup in helpers.worker_setup.__wrapped__(tmp_path, pki, source):
        settings = dict(
            binding="simulator",
            url=dss.url,
            tcp=list(dss.tc_address),
            directory=str(tmp_path / "native-driver"),
            commands=["CMD1"],
            telemetry=[dss.database.telemetry[0]["item_id"]],
        )
        driver = ContextDriver(setup["app"].authority, settings)
        setup["app"].native_driver = driver
        setup["app"].launch = WorkerLaunch(setup["app"].preflight, driver)
        setup["grant"] = grant(setup)
        assert call(setup, pki, setup["grant"])[0] == 200
        setup.update(driver=driver, dss=dss, settings=settings)
        try:
            yield setup
        finally:
            setup["app"].close()


def native_call(setup, pki, path, message, *, key=None, certificate="worker", **updates):
    body = dict(
        schema="openbexi.worker/2",
        context_id="A",
        grant=asdict(setup["grant"]),
        runtime_capability=setup["runtime_capabilities"][setup["grant"].execution_id],
        request_id=key or str(uuid.uuid4()),
        path=path,
        payload=base64.b64encode(message.SerializeToString(deterministic=True)).decode("ascii"),
    )
    body.update(updates)
    return request(
        setup["server"],
        pki[certificate]["client"],
        "/v1/worker/driver",
        subject=None,
        payload=body,
    )


def command():
    return proto.CommandDesc(command=proto.TcItemDesc(mnemonic="CMD1"))


def test_original_tc_over_worker_mtls_has_five_durable_receipts(driver_setup, pki):
    setup = driver_setup
    assert call(setup, pki, setup["grant"], "event", **event_body())[0] == 200
    code, answer = native_call(setup, pki, PREFIX + "TC/SendCommand", command())
    assert code == 200, answer
    receipt = BoolValue.FromString(base64.b64decode(answer["result"]["payload"]))
    assert receipt.value
    assert setup["dss"].get("state")["core"]["commands_executed"] == 1
    for db in (setup["store"].db, setup["driver"].gate.db):
        rows = db.execute("SELECT state FROM effect_intents").fetchall()
        assert [r[0] for r in rows] == ["ACKED"] * 5
        assert setup["grant"].token not in "\n".join(db.iterdump())
        assert setup["runtime_capabilities"][setup["grant"].execution_id] not in "\n".join(
            db.iterdump()
        )
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    assert setup["store"].db.execute("PRAGMA user_version").fetchone()[0] == 8


def test_real_worker_client_uses_protocol_two_and_cannot_downgrade(driver_setup, pki):
    setup = driver_setup
    route = Route(
        f"https://localhost:{setup['server'].server_port}",
        pki["context-a"]["pin"],
        pki["worker"]["client"],
    )
    original = dict(schema="openbexi.worker/2", context_id="A", grant=asdict(setup["grant"]))
    proof = setup["runtime_capabilities"][setup["grant"].execution_id]
    with pytest.raises(Fault) as denied:
        route.call(original, path="/v1/worker/driver", schema="openbexi.worker/2")
    assert denied.value.status == 403
    with pytest.raises(Fault) as spent:
        route.call(original, path="/v1/worker/consume", schema="openbexi.worker/2")
    assert spent.value.status == 403
    check = route.call(
        {**original, "runtime_capability": proof},
        path="/v1/worker/check",
        schema="openbexi.worker/2",
    )
    assert check["checked"] is True
    event = route.call(
        {**original, "runtime_capability": proof, **event_body()},
        path="/v1/worker/event",
        schema="openbexi.worker/2",
    )
    assert event["recorded"] is True
    reply = route.call(
        {
            **original,
            "runtime_capability": proof,
            "request_id": str(uuid.uuid4()),
            "path": PREFIX + "TC/SendCommand",
            "payload": base64.b64encode(command().SerializeToString()).decode("ascii"),
        },
        path="/v1/worker/driver",
        schema="openbexi.worker/2",
    )
    assert BoolValue.FromString(base64.b64decode(reply["payload"])).value
    assert setup["dss"].get("state")["core"]["commands_executed"] == 1
    for action in ("consume", "check", "event", "driver"):
        with pytest.raises(ValueError, match="Unconfigured RPC route"):
            route.call(original, path="/v1/worker/" + action, schema="openbexi.worker/1")
    with pytest.raises(Fault) as old_body:
        route.call(
            {**original, "schema": "openbexi.worker/1", "runtime_capability": proof},
            path="/v1/worker/check",
            schema="openbexi.worker/2",
        )
    assert old_body.value.status == 403


def test_twenty_duplicate_rpc_calls_produce_one_real_command(driver_setup, pki):
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: native_call(
                    driver_setup, pki, PREFIX + "TC/SendCommand", command(), key=key
                )[0],
                range(20),
            )
        )
    assert results.count(200) == 1 and results.count(409) == 19
    assert driver_setup["dss"].get("state")["core"]["commands_executed"] == 1


def test_copied_original_config_cannot_bypass_consumption_and_dispatch(driver_setup, pki):
    # A second process can possess the original certificate/configuration but
    # must not obtain the winner's memory-only consumption receipt.
    setup = driver_setup
    copied = dict(
        schema="openbexi.worker/2",
        context_id="A",
        grant=asdict(setup["grant"]),
        request_id=str(uuid.uuid4()),
        path=PREFIX + "TC/SendCommand",
        payload=base64.b64encode(command().SerializeToString()).decode("ascii"),
    )
    status, _ = request(
        setup["server"], pki["worker"]["client"], "/v1/worker/driver", subject=None, payload=copied
    )
    assert status == 403
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0


@pytest.mark.parametrize("receipt", [None, True, 123, "bad", "0" * 64])
def test_invalid_or_guessed_consumption_proof_cannot_dispatch(driver_setup, pki, receipt):
    assert (
        native_call(
            driver_setup, pki, PREFIX + "TC/SendCommand", command(), runtime_capability=receipt
        )[0]
        == 403
    )
    assert driver_setup["dss"].get("state")["core"]["commands_executed"] == 0


def test_lost_consumption_proof_cannot_be_refreshed_from_original_config(driver_setup, pki):
    setup = driver_setup
    setup["runtime_capabilities"].clear()
    assert call(setup, pki, setup["grant"])[0] == 403
    assert call(setup, pki, setup["grant"], "check")[0] == 403
    assert call(setup, pki, setup["grant"], "event", **event_body())[0] == 403
    assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0


def test_permitted_original_telemetry_is_correlated_and_replay_denied(driver_setup, pki):
    setup = driver_setup
    name = setup["settings"]["telemetry"][0]
    code, answer = native_call(
        setup, pki, PREFIX + "TM/CreateTmItem", proto.TmItemDesc(mnemonic=name)
    )
    assert code == 200, answer
    item = proto.TmItemDesc.FromString(base64.b64decode(answer["result"]["payload"]))
    assert item.mnemonic == name
    key = str(uuid.uuid4())
    reading = proto.TmItemValue(item=item)
    code, answer = native_call(setup, pki, PREFIX + "TM/RefreshItem", reading, key=key)
    assert code == 200, answer
    sample = proto.TmItemValue.FromString(base64.b64decode(answer["result"]["payload"]))
    assert sample.item.mnemonic == name and sample.timestamp
    assert native_call(setup, pki, PREFIX + "TM/RefreshItem", reading, key=key)[0] == 409
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0


def test_every_other_original_rpc_method_is_denied_before_effect(driver_setup, pki):
    for service in proto.DESCRIPTOR.services_by_name.values():
        for method in service.methods:
            path = "/spell.driver." + service.name + "/" + method.name
            if path in METHODS:
                continue
            code, _ = native_call(driver_setup, pki, path, proto.Event())
            assert code == 403, path
    assert (
        driver_setup["store"].db.execute("SELECT COUNT(*) FROM native_driver_calls").fetchone()[0]
        == 0
    )
    assert driver_setup["dss"].get("state")["core"]["commands_executed"] == 0


@pytest.mark.parametrize("certificate", ["alice", "bob", "listener", "observer"])
def test_only_the_bound_worker_certificate_can_dispatch(driver_setup, pki, certificate):
    assert native_call(
        driver_setup, pki, PREFIX + "TC/SendCommand", command(), certificate=certificate
    )[0] in {403, 404}
    assert driver_setup["dss"].get("state")["core"]["commands_executed"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("control_epoch", 2),
        ("worker_incarnation", "worker-2"),
        ("connection_generation", 2),
        ("token", "0" * 64),
    ],
)
def test_original_grant_cannot_be_substituted(driver_setup, pki, field, value):
    forged = asdict(replace(driver_setup["grant"], **{field: value}))
    assert (
        native_call(driver_setup, pki, PREFIX + "TC/SendCommand", command(), grant=forged)[0] == 403
    )
    assert driver_setup["dss"].get("state")["core"]["commands_executed"] == 0


def test_live_revocation_precedes_replay_and_fresh_admission(driver_setup, pki):
    setup = driver_setup
    key = str(uuid.uuid4())
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command(), key=key)[0] == 200
    setup["app"].authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command(), key=key)[0] == 403
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command())[0] == 403
    assert setup["dss"].get("state")["core"]["commands_executed"] == 1


def test_resource_acl_denies_unlisted_command_and_telemetry(driver_setup, pki):
    for path, message in (
        ("TC/SendCommand", proto.CommandDesc(command=proto.TcItemDesc(mnemonic="CMD2"))),
        ("TM/RefreshItem", proto.TmItemValue(item=proto.TmItemDesc(mnemonic="NOT_ALLOWED"))),
    ):
        assert native_call(driver_setup, pki, PREFIX + path, message)[0] == 403
    assert (
        driver_setup["store"].db.execute("SELECT COUNT(*) FROM effect_intents").fetchone()[0] == 0
    )


@pytest.mark.parametrize("payload", ["*", "A" * 43693])
def test_invalid_or_oversized_wire_payload_is_rejected(driver_setup, pki, payload):
    assert (
        native_call(driver_setup, pki, PREFIX + "TC/SendCommand", command(), payload=payload)[0]
        == 400
    )


def test_optional_driver_cannot_enable_itself_on_default_context(tmp_path, pki):
    store = ContextStore(tmp_path / "disabled", "A")
    try:
        with pytest.raises(ValueError, match="explicit retained"):
            Context(store, pki["listener"]["pin"], {}, native_driver_factory=lambda _: None)
    finally:
        store.close()


def test_handoff_between_real_stages_fences_original_rpc_and_retains_owner(driver_setup, pki):
    setup = driver_setup
    authority = setup["app"].authority
    execution = setup["execution"]
    bob_connection = setup["controller"]("session.open", {}, subject="bob")["connection_id"]
    claim = setup["controller"](
        "execution.claim",
        dict(execution_id=execution["id"], connection_id=bob_connection, expected_epoch=1),
        subject="bob",
    )
    gate = setup["driver"].gate
    settle = gate.settle

    def accept_after_receipt(original, operation, stage, receipt):
        settle(original, operation, stage, receipt)
        if stage == "TRANSPORT":
            decision = setup["controller"](
                "execution.decide",
                dict(**helpers.proof(execution), claim_id=claim["claim_id"], decision="accept"),
            )
            assert decision["state"] == "BLOCKED"

    gate.settle = accept_after_receipt
    key = str(uuid.uuid4())
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command(), key=key)[0] == 500
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0
    row = authority.list_executions("alice")["executions"][0]
    assert row["owner"] == "alice" and row["epoch"] == 1
    assert row["control_state"] == "RECOVERY_REQUIRED"
    assert (
        setup["store"]
        .db.execute("SELECT state FROM native_driver_calls WHERE request_id=?", (key,))
        .fetchone()[0]
        == "UNCERTAIN"
    )
    assert [r[0] for r in gate.db.execute("SELECT state FROM effect_intents")] == ["ACKED"]
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_driver_route_is_absent_without_explicit_adapter(tmp_path, pki, source):
    for setup in helpers.worker_setup.__wrapped__(tmp_path, pki, source):
        setup["app"].launch = WorkerLaunch(setup["app"].preflight)
        setup["grant"] = grant(setup)
        assert call(setup, pki, setup["grant"])[0] == 200
        assert native_call(setup, pki, PREFIX + "TC/SendCommand", command())[0] == 404


def test_lost_native_release_receipt_keeps_holds_and_never_replays(driver_setup, pki):
    setup = driver_setup
    gate = setup["driver"].gate
    send = gate.send

    def lose_receipt(original, binding, operation, stage, connection, packet):
        send(original, binding, operation, stage, connection, packet)
        if stage == "RELEASE":
            connection.close()

    gate.send = lose_receipt
    key = str(uuid.uuid4())
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command(), key=key)[0] == 500
    deadline = time.monotonic() + 2
    while setup["dss"].get("state")["core"]["commands_executed"] == 0:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert [tuple(r) for r in gate.db.execute("SELECT stage,state FROM effect_intents")] == [
        ("TRANSPORT", "ACKED"),
        ("LOADING", "ACKED"),
        ("RELEASE", "UNCERTAIN"),
    ]
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command(), key=key)[0] == 403
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command())[0] == 403
    assert setup["dss"].get("state")["core"]["commands_executed"] == 1
    row = setup["app"].authority.list_executions("alice")["executions"][0]
    assert row["control_state"] == "RECOVERY_REQUIRED"
    assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_rpc_capacity_is_reserved_before_any_binary_effect(driver_setup, pki):
    setup = driver_setup
    with setup["store"].transaction():
        setup["store"].db.executemany(
            "INSERT INTO native_driver_calls VALUES(?,?,?,?,?,?,'COMPLETED',NULL)",
            [(str(uuid.uuid4()), "held", "hash", "simulator", "read", "hash") for _ in range(512)],
        )
    assert native_call(setup, pki, PREFIX + "TC/SendCommand", command())[0] == 503
    assert setup["store"].db.execute("SELECT COUNT(*) FROM effect_intents").fetchone()[0] == 0
    assert setup["dss"].get("state")["core"]["commands_executed"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"url": "http://example.com:8000"},
        {"url": "http://name:password@127.0.0.1:8000"},
        {"url": "http://127.0.0.1:8000/api?redirect=1"},
        {"binding": "context-audit"},
        {"commands": ["CMD1", "CMD1"]},
        {"commands": [], "telemetry": []},
        {"tcp": ["127.0.0.1", True]},
    ],
)
def test_unbounded_or_nonfixed_operator_configuration_fails_closed(driver_setup, changes):
    settings = dict(driver_setup["settings"], **changes)
    with pytest.raises((ValueError, TypeError)):
        ContextDriver(driver_setup["app"].authority, settings)
