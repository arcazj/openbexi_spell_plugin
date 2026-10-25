"""Actual IDE client -> certificate gateway -> Listener -> Context TLS chain."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest

from openbexi_runtime.spell_server_client import SpellServerClient, SpellServerError
from openbexi_spell_server.contracts import Actor
from openbexi_spell_server.gateway import Gateway
from openbexi_spell_server.services import Context, Listener
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.transport import Route
from test_services import ALL, request, serving


@pytest.fixture
def desktop_cluster(tmp_path, pki, source):
    with ExitStack() as stack:
        store = ContextStore(tmp_path / "authority", "A")
        stack.callback(store.close)
        context = Context(
            store,
            pki["listener"]["pin"],
            {"alice": ALL, "bob": ALL, "observer": ["context:read", "execution:read"]},
            worker_slots={f"slot-{i}": f"worker-{i}" for i in range(10)},
            approved_sources=source["config"],
        )
        cs = stack.enter_context(serving(context, pki["context-a"]["server"]))
        route = Route(
            f"https://localhost:{cs.server_port}",
            pki["context-a"]["pin"],
            pki["listener"]["client"],
        )
        roles = ("alice", "bob", "observer")
        listener = Listener(
            pki["edge"]["pin"],
            {pki[r]["pin"]: r for r in roles},
            {r: ["A"] for r in roles},
            {"A": route},
        )
        ls = stack.enter_context(serving(listener, pki["listener"]["server"]))
        gateway = Gateway(
            f"https://localhost:{ls.server_port}",
            pki["listener"]["pin"],
            pki["edge"]["client"],
            [pki[r]["pin"] for r in roles],
        )
        gs = stack.enter_context(serving(gateway, pki["edge"]["server"]))
        clients = {
            r: SpellServerClient(
                url=f"https://localhost:{gs.server_port}",
                fingerprint=pki["edge"]["pin"],
                ca=pki["ca"],
                certificate=pki[r]["cert"],
                key=pki[r]["key"],
            )
            for r in roles
        }
        yield dict(
            clients=clients,
            gateway=gs,
            app=gateway,
            listener=ls,
            context=context,
            store=store,
            source=source,
        )


def mutate(client, method, payload, key=None):
    return client.authority("A", method, payload, key=key or str(uuid.uuid4()))


def reserve(client):
    connection = mutate(client, "session.open", {})["connection_id"]
    procedure = client.read("A", "procedures")["procedures"][0]
    payload = {
        k: procedure[k]
        for k in (
            "procedure_id",
            "source_revision",
            "source_sha256",
            "runtime_image",
            "driver_binding",
        )
    }
    result = mutate(client, "execution.reserve", {**payload, "connection_id": connection})
    client.remember_controller("A", result)
    return result


def test_three_real_ide_clients_observe_and_explicitly_transfer(desktop_cluster):
    clients = desktop_cluster["clients"]
    alice, bob, observer = (clients[r] for r in ("alice", "bob", "observer"))
    assert alice.contexts() == observer.contexts() == ["A"]
    health = observer.read("A", "health")
    assert health["subject"] == "observer" and "execution:control" not in health["permissions"]
    execution = reserve(alice)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: observer.read("A", "executions"), range(20)))
    assert all(result == results[0] for result in results)
    assert "capability" not in json.dumps(results)
    for method, payload in (
        ("session.open", {}),
        ("session.close", {"connection_id": execution["connection_id"]}),
    ):
        with pytest.raises(SpellServerError) as error:
            mutate(observer, method, payload)
        assert error.value.status == 403
    connection = mutate(bob, "session.open", {})["connection_id"]
    claim = mutate(
        bob,
        "execution.claim",
        {"execution_id": execution["id"], "connection_id": connection, "expected_epoch": 1},
    )
    assert observer.read("A", "executions")["executions"][0]["owner"] == "alice"
    decision_key = str(uuid.uuid4())
    original = dict(alice._controllers[("A", execution["id"])])
    accepted = alice.decide("A", execution["id"], claim["claim_id"], "accept", key=decision_key)
    assert accepted["state"] == "ACCEPTED" and "capability" not in accepted
    assert ("A", execution["id"]) not in alice._controllers
    replay = mutate(
        alice,
        "execution.decide",
        {**original, "claim_id": claim["claim_id"], "decision": "accept"},
        decision_key,
    )
    assert replay["replayed"] and "capability" not in replay
    with pytest.raises(SpellServerError):
        mutate(
            alice,
            "execution.rebind",
            {
                "execution_id": execution["id"],
                "connection_id": execution["connection_id"],
                "expected_epoch": 1,
            },
        )
    rebound = mutate(
        bob,
        "execution.rebind",
        {"execution_id": execution["id"], "connection_id": connection, "expected_epoch": 2},
    )
    assert bob.remember_controller("A", rebound)
    mutate(alice, "session.close", {"connection_id": execution["connection_id"]})
    final = observer.read("A", "executions")["executions"][0]
    assert final["owner"] == "bob" and final["epoch"] == 2 and final["control_state"] == "OWNED"
    assert desktop_cluster["store"].db.execute("PRAGMA user_version").fetchone()[0] == 4
    assert not observer.read("A", "health")["runtime_enabled"]


def test_edge_cannot_be_spoofed_by_desktop_or_internal_role(desktop_cluster, pki):
    setup = desktop_cluster
    assert (
        request(
            setup["gateway"], pki["alice"]["client"], "/v1/contexts", subject=pki["bob"]["pin"]
        )[0]
        == 403
    )
    assert (
        request(setup["gateway"], pki["worker"]["client"], "/v1/contexts", subject=None)[0] == 403
    )
    assert (
        request(
            setup["listener"], pki["alice"]["client"], "/v1/contexts", subject=pki["alice"]["pin"]
        )[0]
        == 403
    )
    alice = setup["clients"]["alice"]
    with pytest.raises(SpellServerError) as error:
        alice.read("B", "health")
    assert error.value.status == 403
    alice.fingerprint = "0" * 64
    with pytest.raises(SpellServerError, match="gateway_identity_unavailable"):
        alice.contexts()


def test_gateway_live_role_revocation_precedes_replay(desktop_cluster):
    alice = desktop_cluster["clients"]["alice"]
    key = str(uuid.uuid4())
    mutate(alice, "session.open", {}, key)
    desktop_cluster["context"].subjects["alice"] = Actor("alice", frozenset({"context:read"}))
    with pytest.raises(SpellServerError) as error:
        mutate(alice, "session.open", {}, key)
    assert error.value.status == 403


def test_actual_desktop_panel_connects_observer_and_disables_mutations(
    desktop_cluster, pki, tmp_path
):
    import os
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from openbexi_ide.spell_server_panel import SpellServerPanel

    app = QApplication.instance() or QApplication([])
    panel = SpellServerPanel()
    config = tmp_path / "observer.json"
    config.write_text(
        json.dumps(
            dict(
                url=f"https://localhost:{desktop_cluster['gateway'].server_port}",
                fingerprint=pki["edge"]["pin"],
                ca=str(pki["ca"]),
                certificate=str(pki["observer"]["cert"]),
                key=str(pki["observer"]["key"]),
            )
        )
    )
    try:
        panel.connect_config(config)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            app.processEvents()
            if panel.state.get("health"):
                break
            time.sleep(0.01)
        assert panel.state["health"]["subject"] == "observer"
        assert panel.refresh_button.isEnabled()
        assert not any(
            button.isEnabled()
            for button in (
                panel.reserve_button,
                panel.rebind_button,
                panel.claim_button,
                panel.accept_button,
                panel.reject_button,
            )
        )
        assert panel.executions.topLevelItemCount() == 0
        panel.disconnect_server()
        deadline = time.monotonic() + 5
        while panel.client is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert panel.client is None and panel.status.text() == "Disconnected"
    finally:
        panel.close_connection()
        panel.close()


def test_hundred_actual_ide_reservations_have_one_winner(desktop_cluster, pki):
    setup = desktop_cluster
    connection = mutate(setup["clients"]["alice"], "session.open", {})["connection_id"]
    procedure = setup["clients"]["alice"].read("A", "procedures")["procedures"][0]
    payload = {
        k: procedure[k]
        for k in (
            "procedure_id",
            "source_revision",
            "source_sha256",
            "runtime_image",
            "driver_binding",
        )
    }

    # Independent client locks and TLS connections; eight concurrent callers,
    # 100 distinct idempotency keys, one logical procedure reservation.
    def attempt(_):
        client = SpellServerClient(
            url=f"https://localhost:{setup['gateway'].server_port}",
            fingerprint=pki["edge"]["pin"],
            ca=pki["ca"],
            certificate=pki["alice"]["cert"],
            key=pki["alice"]["key"],
        )
        try:
            return mutate(client, "execution.reserve", {**payload, "connection_id": connection})
        except SpellServerError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(100)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count(409) == 99
    with setup["store"].transaction(write=False):
        assert setup["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
        assert setup["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


def test_three_actual_desktop_panels_reserve_request_accept_and_rebind(
    desktop_cluster, pki, tmp_path
):
    import os
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
    from openbexi_ide.spell_server_panel import SpellServerPanel

    app = QApplication.instance() or QApplication([])
    panels = {}
    window = QWidget()
    layout = QVBoxLayout(window)
    window.resize(1100, 850)

    def wait(predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError("Desktop condition did not arrive")

    def settled(panel):
        wait(lambda: not panel.busy and bool(panel.state.get("health")))

    def refresh_select(panel):
        panel.refresh()
        settled(panel)
        assert panel.executions.topLevelItemCount() == 1
        panel.executions.setCurrentItem(panel.executions.topLevelItem(0))
        app.processEvents()

    try:
        for role in ("alice", "bob", "observer"):
            panel = SpellServerPanel()
            panels[role] = panel
            layout.addWidget(panel)
            config = tmp_path / (role + ".json")
            config.write_text(
                json.dumps(
                    dict(
                        url=f"https://localhost:{desktop_cluster['gateway'].server_port}",
                        fingerprint=pki["edge"]["pin"],
                        ca=str(pki["ca"]),
                        certificate=str(pki[role]["cert"]),
                        key=str(pki[role]["key"]),
                    )
                )
            )
            panel.connect_config(config)
            settled(panel)
        window.show()
        app.processEvents()
        alice, bob, observer = (panels[r] for r in ("alice", "bob", "observer"))
        assert alice.reserve_button.isEnabled()
        alice.reserve_button.click()
        settled(alice)
        refresh_select(bob)
        assert bob.claim_button.isEnabled()
        bob.claim_button.click()
        settled(bob)
        refresh_select(alice)
        assert alice.accept_button.isEnabled() and alice.reject_button.isEnabled()
        alice.accept_button.click()
        settled(alice)
        refresh_select(bob)
        assert bob.rebind_button.isEnabled()
        bob.rebind_button.click()
        settled(bob)
        refresh_select(observer)
        assert observer.selected()["owner"] == "bob" and observer.selected()["epoch"] == 2
        assert observer.selected()["control_state"] == "OWNED"
        assert not any(
            button.isEnabled()
            for button in (
                observer.reserve_button,
                observer.rebind_button,
                observer.claim_button,
                observer.accept_button,
                observer.reject_button,
            )
        )
        if output := os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR"):
            from pathlib import Path

            app.processEvents()
            assert window.grab().save(str(Path(output) / "ide-three-panels.png"))
        # Capability data never enters the tree's public row model.
        assert "capability" not in json.dumps(observer.selected())
        for panel in (alice, bob, observer):
            panel.disconnect_button.click()
            wait(lambda: panel.client is None)
        assert (
            desktop_cluster["context"].authority.list_executions("alice")["executions"][0][
                "control_state"
            ]
            == "CONTROLLER_DISCONNECTED"
        )
    finally:
        for panel in panels.values():
            panel.close_connection()
            panel.close()
        window.close()



def test_three_pinned_ide_clients_monitor_redacted_context_events(desktop_cluster):
    """Real TLS replay across desktop -> gateway -> Listener -> Context."""
    clients, store = desktop_cluster["clients"], desktop_cluster["store"]
    with store.transaction():
        store._event("CONTROL_CLAIM_REQUESTED", {
            "execution_id": str(uuid.uuid4()), "capability": "SECRET_NEVER_EXPORT"
        })
        store._event("NATIVE_DRIVER_EVENT", {
            "message": "SECRET_DRIVER_DATA", "token": "SECRET_NEVER_EXPORT"
        })
        store._event("CONTROL_OWNER_CHANGED", {"owner": "alice", "epoch": 5})
    observed = {}
    for role in ("alice", "bob", "observer"):
        client = clients[role]
        first = client.events("A", after_sequence=0, limit=1)
        assert first["has_more"] is True
        second = client.events("A", after_sequence=first["next_sequence"], limit=1)
        assert second["has_more"] is False
        events = first["events"] + second["events"]
        assert [event["type"] for event in events] == [
            "CONTROL_CLAIM_REQUESTED", "CONTROL_OWNER_CHANGED"
        ]
        assert "SECRET_NEVER_EXPORT" not in json.dumps(events)
        assert "SECRET_DRIVER_DATA" not in json.dumps(events)
        assert "owner" not in json.dumps(events)
        assert client.has_controller("A", "nonexistent") is False
        observed[role] = events
    assert observed["alice"] == observed["bob"] == observed["observer"]
    desktop_cluster["context"].subjects["observer"] = Actor(
        "observer", frozenset({"context:read"})
    )
    with pytest.raises(SpellServerError) as error:
        clients["observer"].events("A", after_sequence=0, limit=1)
    assert error.value.status == 403
