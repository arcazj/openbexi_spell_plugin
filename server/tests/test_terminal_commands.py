"""Owner ABORT/CLOSE admission and terminal-intent fencing over real mTLS."""

from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

from openbexi_spell_server.contracts import Fault
from openbexi_spell_server.effects import DriverGate
from test_launch import call
import test_owner_commands as owner
from test_owner_commands import delivered, enqueue, worker, rows

queue, family, source, setup = owner.queue, owner.family, owner.source, owner.setup
agent, provider = owner.agent, owner.provider


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
def test_terminal_admission_consumes_once_without_releasing_hold(queue, family, pki, command):
    grant = delivered(family, pki, command)
    assert worker(family, pki, "command-consume", grant)[0] == 409
    assert worker(family, pki, "command-forward", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] in (403, 409)
    assert worker(family, pki)[1]["result"]["action"] == "hold"
    assert rows(family)[0]["state"] == "EXECUTION_UNPROVEN"
    assert family["store"].db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    assert family["store"].db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 1
    code, body = call(
        family,
        pki,
        family["grant"],
        "command-disposition",
        command_grant=grant,
        disposition="HANDLER_RETURNED",
    )
    assert code == 200
    assert body["result"]["quiescence_proven"] is False
    assert body["result"]["effective_transfer"] is False
    assert body["result"]["hold_retained"] is True


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
@pytest.mark.parametrize("subject", ["bob", "observer"])
def test_terminal_commands_do_not_bypass_live_owner(queue, family, pki, command, subject):
    assert enqueue(family, pki, command, subject=subject)[0] == 403
    assert not rows(family)


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
def test_disconnected_owner_cannot_trigger_first_terminal_side_effect(queue, family, pki, command):
    grant = delivered(family, pki, command)
    assert worker(family, pki, "command-forward", grant)[0] == 200
    family["controller"]("session.close", dict(connection_id=family["connection"]))
    assert worker(family, pki, "command-consume", grant)[0] == 403
    assert rows(family)[0]["state"] == "FORWARD_UNPROVEN"
    assert queue.terminal_intents(family["grant"].execution_id) == []


@pytest.mark.parametrize("command", ["CMD_ABORT", "CMD_CLOSE"])
def test_concurrent_terminal_consumption_has_one_winner(queue, family, pki, command):
    grant = delivered(family, pki, command)
    assert worker(family, pki, "command-forward", grant)[0] == 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(
            pool.map(lambda _: worker(family, pki, "command-consume", grant)[0], range(20))
        )
    assert outcomes.count(200) == 1
    assert all(code in (200, 403, 409) for code in outcomes)
    assert len(queue.terminal_intents(family["grant"].execution_id)) == 1


@pytest.mark.parametrize("terminal", ["CMD_ABORT", "CMD_CLOSE"])
@pytest.mark.parametrize("ordinary", ["CMD_RUN", "CMD_STEP", "CMD_PAUSE"])
def test_terminal_intent_fences_queued_and_new_nonterminal_work(
    queue, family, pki, terminal, ordinary
):
    first = delivered(family, pki, terminal)
    second = delivered(family, pki, ordinary)
    assert worker(family, pki, "command-forward", second)[0] == 200
    assert worker(family, pki, "command-forward", first)[0] == 200
    assert worker(family, pki, "command-consume", first)[0] == 200
    assert worker(family, pki, "command-consume", second)[0] == 403
    assert enqueue(family, pki, ordinary)[0] == 403
    assert rows(family)[1]["state"] == "FORWARD_UNPROVEN"
    assert family["app"].authority.list_executions("alice")["executions"][0]["owner"] == "alice"


def test_close_remains_possible_after_abort_but_cannot_be_consumed_twice(queue, family, pki):
    abort = delivered(family, pki, "CMD_ABORT")
    assert worker(family, pki, "command-forward", abort)[0] == 200
    assert worker(family, pki, "command-consume", abort)[0] == 200
    # The original native CIF independently requires an actual terminal status.
    close = delivered(family, pki, "CMD_CLOSE")
    assert worker(family, pki, "command-forward", close)[0] == 200
    assert worker(family, pki, "command-consume", close)[0] == 200
    assert worker(family, pki, "command-consume", close)[0] == 403
    assert len(queue.terminal_intents(family["grant"].execution_id)) == 2


def test_terminal_request_uses_exact_member_and_original_worker_grant(queue, family, pki):
    grant = delivered(family, pki, "CMD_ABORT")
    for changes in (
        dict(token="0" * 64),
        dict(command="CMD_CLOSE"),
        dict(target_admission_id=str(uuid.uuid4())),
        dict(control_epoch=grant["control_epoch"] + 1),
    ):
        assert worker(family, pki, "command-forward", dict(grant, **changes))[0] in (400, 403)
    assert queue.terminal_intents(family["grant"].execution_id) == []


def test_terminal_lost_ack_does_not_replay_native_effect(agent, family, pki):
    grant = delivered(family, pki, "CMD_ABORT")
    agent.dispatch_owner(grant)
    message = dict(
        schema="openbexi.native-control/1",
        instance_id="main#1",
        request_id=grant["command_id"],
        command="CMD_ABORT",
    )
    agent.forward(message)
    original = agent.route.call
    count = []

    def lose_ack(*args, **kwargs):
        count.append(1)
        original(*args, **kwargs)
        raise TimeoutError("persisted before lost acknowledgment")

    agent.route.call = lose_ack
    message["schema"] = "openbexi.native-consume/1"
    with pytest.raises(TimeoutError):
        agent.consume(message)
    with pytest.raises(ValueError, match="already attempted"):
        agent.consume(message)
    assert len(count) == 1
    assert rows(family)[0]["state"] == "EXECUTION_UNPROVEN"
    assert not agent.owner_consumed


def test_terminal_intent_fences_real_driver_final_admission(queue, family, pki):
    # _live is invoked under the per-execution lock immediately before sendall.
    # This uses the real authority/grant, not a mocked permission check.
    gate = DriverGate.__new__(DriverGate)
    gate.authority = family["app"].authority
    from json import loads

    execution = family["store"].db.execute("SELECT inventory FROM executions").fetchone()
    binding = loads(execution["inventory"])["driver_binding"]
    gate.bindings = {binding: ("127.0.0.1", 12345)}
    with family["store"].transaction():
        gate._live(family["grant"], binding)
    grant = delivered(family, pki, "CMD_ABORT")
    assert worker(family, pki, "command-forward", grant)[0] == 200
    assert worker(family, pki, "command-consume", grant)[0] == 200
    with family["store"].transaction(), pytest.raises(Fault, match="native_terminal_work_fenced"):
        gate._live(family["grant"], binding)
    # Safety-only reports remain possible; they grant no permission to send.
    assert (
        call(
            family, pki, family["grant"], "command-report", command_grant=grant, outcome="UNCERTAIN"
        )[0]
        == 200
    )
