"""Installed-client API through real TLS edge/Listener/Context command admission.

Native dispatch and cgroup evidence run separately in the hosted IDE cohort.
"""

from contextlib import ExitStack
import uuid

import pytest

from openbexi_runtime.spell_server_client import SpellServerClient, SpellServerError
from openbexi_spell_server.contracts import Actor
from openbexi_spell_server.gateway import Gateway
from openbexi_spell_server.services import Listener
from openbexi_spell_server.transport import Route
from test_services import serving
import test_live_handoff as live
import test_owner_commands as owners

source, setup, ledger = live.source, live.setup, live.ledger


@pytest.fixture
def desktop(ledger, pki):
    roles = ("alice", "bob", "observer")
    for role in ("alice", "bob"):
        actor = ledger["app"].subjects[role]
        ledger["app"].subjects[role] = Actor(role, actor.permissions | {"context:read"})
    with ExitStack() as stack:
        route = Route(
            f"https://localhost:{ledger['server'].server_port}",
            pki["context-a"]["pin"],
            pki["listener"]["client"],
        )
        listener = Listener(
            pki["edge"]["pin"],
            {pki[r]["pin"]: r for r in roles},
            {r: ["A"] for r in roles},
            {"A": route},
            native_command_contexts=["A"],
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
        clients["alice"].remember_controller("A", ledger["execution"])
        yield dict(ledger=ledger, listener=listener, clients=clients)


@pytest.mark.parametrize("command", ["CMD_RUN", "CMD_STEP", "CMD_PAUSE", "CMD_ABORT", "CMD_CLOSE"])
def test_owner_commands_cross_actual_three_hop_tls_once(desktop, pki, command):
    client = desktop["clients"]["alice"]
    ledger = desktop["ledger"]
    eid = ledger["execution"]["id"]
    health = client.read("A", "health")
    assert command in health["native_commands"] and not health["runtime_enabled"]
    key = str(uuid.uuid4())
    first = client.command("A", eid, command, key=key)
    again = client.command("A", eid, command, key=key)
    assert first["command_id"] == again["command_id"] and again["replayed"]
    assert len(owners.rows(ledger)) == 1
    code, answer = owners.worker(ledger, pki)
    assert code == 200 and answer["result"]["grant"]["command"] == command
    assert owners.worker(ledger, pki)[1]["result"]["action"] == "none"


@pytest.mark.parametrize("role", ["bob", "observer"])
@pytest.mark.parametrize("command", ["CMD_RUN", "CMD_STEP", "CMD_PAUSE", "CMD_ABORT", "CMD_CLOSE"])
def test_stolen_controller_proof_cannot_cross_authenticated_identity(desktop, role, command):
    ledger = desktop["ledger"]
    client = desktop["clients"][role]
    client.remember_controller("A", ledger["execution"])
    with pytest.raises(SpellServerError) as denied:
        client.command("A", ledger["execution"]["id"], command, key=str(uuid.uuid4()))
    assert denied.value.status == 403 and not owners.rows(ledger)
    if role == "observer":
        assert client.read("A", "health")["native_commands"] == []


def test_disabled_listener_denies_commands_and_hides_availability(desktop):
    desktop["listener"].native_command_contexts = frozenset()
    client = desktop["clients"]["alice"]
    assert client.read("A", "health")["native_commands"] == []
    assert client.read("A", "health")["native_rebind"] is False
    with pytest.raises(SpellServerError) as denied:
        client.command("A", desktop["ledger"]["execution"]["id"], "CMD_RUN", key="closed")
    assert denied.value.status == 404 and not owners.rows(desktop["ledger"])


def test_command_live_role_revocation_precedes_replay(desktop):
    ledger = desktop["ledger"]
    client = desktop["clients"]["alice"]
    eid = ledger["execution"]["id"]
    client.command("A", eid, "CMD_STEP", key="step-once")
    ledger["app"].subjects["alice"] = Actor("alice", frozenset({"context:read"}))
    with pytest.raises(SpellServerError) as denied:
        client.command("A", eid, "CMD_STEP", key="step-once")
    assert denied.value.status == 403 and len(owners.rows(ledger)) == 1


def test_desktop_handoff_keeps_C_readonly_and_requires_B_explicit_resume(desktop, pki):
    a, b, c = (desktop["clients"][r] for r in ("alice", "bob", "observer"))
    ledger = desktop["ledger"]
    eid = ledger["execution"]["id"]
    bc = b.authority("A", "session.open", {}, key="b-session")["connection_id"]
    claim = b.authority(
        "A",
        "execution.claim",
        dict(execution_id=eid, connection_id=bc, expected_epoch=1),
        key="claim",
    )
    decision = a.decide("A", eid, claim["claim_id"], "accept", key="accept")
    assert decision["state"] == "REQUESTED" and not a.has_controller("A", eid)
    state = live.host(ledger, pki, "status")
    live.host(
        ledger,
        pki,
        "complete",
        barrier_id=state["barrier_id"],
        evidence=live.evidence(ledger, state),
    )
    row = next(e for e in c.read("A", "executions")["executions"] if e["id"] == eid)
    assert row["owner"] == "bob" and row["control_state"] == "HANDOFF_PAUSED"
    bound = b.authority(
        "A",
        "execution.rebind",
        dict(execution_id=eid, connection_id=bc, expected_epoch=2),
        key="bind",
    )
    assert b.remember_controller("A", bound)
    assert live.host(ledger, pki, "status")["state"] == "TRANSFERRED_PAUSED"
    resume = b.command("A", eid, "CMD_RUN", key="resume")
    assert resume["command_id"] and live.host(ledger, pki, "status")["state"] == "RESUME_REQUESTED"
    # Explicitly deliver the old proof again to test server-side fencing.
    a.remember_controller("A", ledger["execution"])
    with pytest.raises(SpellServerError) as denied:
        a.command("A", eid, "CMD_RUN", key="stale")
    assert denied.value.status == 403


@pytest.mark.parametrize("bad", [True, "A", ["B"], [1]])
def test_listener_rejects_invalid_native_context_allowlist(pki, bad):
    with pytest.raises(ValueError):
        Listener(pki["edge"]["pin"], {}, {}, {"A": object()}, native_command_contexts=bad)


def test_installed_client_same_owner_reconnect_needs_host_pause_and_explicit_resume(desktop, pki):
    a, c = (desktop["clients"][r] for r in ("alice", "observer"))
    ledger = desktop["ledger"]
    eid = ledger["execution"]["id"]
    assert a.read("A", "health")["native_rebind"] is True
    assert c.read("A", "health")["native_rebind"] is False
    a.authority("A", "session.close", dict(connection_id=ledger["connection"]), key="disconnect")
    connection = a.authority("A", "session.open", {}, key="new-session")["connection_id"]
    payload = dict(execution_id=eid, connection_id=connection, expected_epoch=1)
    pending = a.authority("A", "execution.rebind", payload, key="request-reconnect")
    assert pending["rebind_pending"] and not a.remember_controller("A", pending)
    assert not a.has_controller("A", eid)
    with pytest.raises(SpellServerError, match="controller_proof_required"):
        a.command("A", eid, "CMD_RUN", key="premature")
    state = live.host(ledger, pki, "status")
    evidence = live.evidence(ledger, state)
    live.host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=evidence)
    row = next(e for e in c.read("A", "executions")["executions"] if e["id"] == eid)
    assert (row["owner"], row["epoch"], row["connection_generation"]) == ("alice", 1, 2)
    bound = a.authority("A", "execution.rebind", payload, key="bind-reconnected")
    assert a.remember_controller("A", bound)
    resume = a.command("A", eid, "CMD_RUN", key="explicit-resume")
    permission = live.host(
        ledger,
        pki,
        "resume",
        barrier_id=state["barrier_id"],
        resume_id=resume["command_id"],
        evidence=evidence,
    )
    activated = live.activate(ledger, pki, permission["runtime_epoch"])
    assert activated["activation_kind"] == "rebind" and activated["grant"]["control_epoch"] == 1


def test_actual_panel_reconnects_closed_session_with_cached_proof(desktop, pki):
    """Real Qt clicks and three-hop TLS; host evidence remains a service fixture."""
    import os
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from openbexi_ide.spell_server_panel import SpellServerPanel

    app = QApplication.instance() or QApplication([])
    client = desktop["clients"]["alice"]
    ledger = desktop["ledger"]
    eid, old = ledger["execution"]["id"], ledger["connection"]
    client.authority("A", "session.close", {"connection_id": old}, key="disconnect-original")
    assert client.has_controller("A", eid)  # A stale local proof must not hide recovery.
    panel = SpellServerPanel()
    panel.client = client
    panel.connections["A"] = old
    panel.context.blockSignals(True)
    panel.context.addItem("A")
    panel.context.blockSignals(False)

    def settled():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            app.processEvents()
            if not panel.busy and panel.state.get("health"):
                panel.executions.setCurrentItem(panel.executions.topLevelItem(0))
                app.processEvents()
                return
            time.sleep(0.01)
        raise AssertionError("Native reconnect panel did not settle: " + panel.status.text())

    try:
        panel.refresh()
        settled()
        assert panel.selected()["control_state"] == "CONTROLLER_DISCONNECTED"
        assert panel.rebind_button.isEnabled()
        assert not any(b.isEnabled() for b in panel.command_buttons.values())
        panel.rebind_button.click()
        settled()
        fresh = panel.connections["A"]
        assert fresh != old and ("A", old) in panel.retained_connections
        assert not client.has_controller("A", eid)
        assert panel.selected()["epoch"] == 1
        state = live.host(ledger, pki, "status")
        assert state["state"] == "REQUESTED"
        proof = live.evidence(ledger, state)
        live.host(ledger, pki, "complete", barrier_id=state["barrier_id"], evidence=proof)
        panel.refresh()
        settled()
        assert panel.selected()["control_state"] == "HANDOFF_PAUSED"
        panel.rebind_button.click()
        settled()
        assert panel.connections["A"] == fresh and client.has_controller("A", eid)
        assert panel.selected()["connection_generation"] == 2
        assert panel.command_buttons["CMD_RUN"].isEnabled()
        panel.command_buttons["CMD_RUN"].click()
        settled()
        resumed = live.host(ledger, pki, "status")
        assert resumed["state"] == "RESUME_REQUESTED"
        # Native physical resume is separately exercised by the installed cohort.
        panel.disconnect_button.click()
        deadline = time.monotonic() + 10
        while panel.client is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert panel.client is None
        assert not panel.connections and not panel.retained_connections
        assert not client.has_controller("A", eid)
    finally:
        panel.close_connection()
        panel.close()
