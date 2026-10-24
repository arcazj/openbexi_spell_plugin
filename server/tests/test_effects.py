"""Real TCP effects with separate DSS PID; no native worker qualification implied."""

import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import threading
import uuid
from contextlib import contextmanager
from dataclasses import replace

import pytest

from openbexi_spell_server.contracts import Fault, policy
from openbexi_spell_server.effects import DriverGate, EffectAdmission
from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.store import ContextStore
from test_authority import Client, PERMISSIONS, SLOTS, worker_start

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "driver_plugin/src")]
from openbexi_spell_dss.fenced_transport import Transport  # noqa: E402
from openbexi_spell_dss.journal import UncertainEffect  # noqa: E402


@pytest.fixture
def authority(tmp_path):
    store = ContextStore(tmp_path / "context", "A")
    service = ExecutionAuthority(
        store, policy({name: PERMISSIONS for name in ("alice", "bob", "carol")}), worker_slots=SLOTS
    )
    try:
        yield service
    finally:
        store.close()


@pytest.fixture
def dss(tmp_path):
    program = """
import json,os,sys,threading
from dss.local import create_servers
runtime,tcp,http=create_servers(sys.argv[1],0)
threads=[threading.Thread(target=s.serve_forever) for s in (tcp,http)]
for t in threads:t.start()
print(json.dumps(dict(pid=os.getpid(),tcp=list(tcp.server_address),http=http.server_port)),flush=True)
try:sys.stdin.buffer.read(1)
finally:
 for s in (http,tcp):s.shutdown();s.server_close()
 for t in threads:t.join(5)
 runtime.engine.close()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", program, str(tmp_path / "dss.sqlite")],
        env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    transport = None
    try:
        assert select.select([child.stdout], [], [], 10)[0], "DSS startup timed out"
        info = json.loads(child.stdout.readline())
        assert info["pid"] != os.getpid()
        evidence = os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR")
        if evidence:
            with (Path(evidence) / "dss-processes.jsonl").open("a") as trace:
                trace.write(
                    json.dumps(
                        dict(parent_pid=os.getpid(), dss_pid=info["pid"], tcp_endpoint=info["tcp"])
                    )
                    + "\n"
                )
        transport = Transport("http://127.0.0.1:" + str(info["http"]), info["tcp"])
        yield transport
    finally:
        if transport:
            transport.close()
        try:
            _, error = child.communicate(b"x", timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            raise
        assert child.returncode == 0, error.decode()


@pytest.fixture
def gate(authority, dss, tmp_path):
    gate = DriverGate(authority, tmp_path / "driver", {"simulator": dss.tc_address})
    try:
        yield gate
    finally:
        gate.close()


def admission(gate, name="procedure"):
    alice = Client(gate.authority, "alice")
    execution = alice.reserve(name)
    grant = worker_start(gate.authority, execution)
    return alice, execution, EffectAdmission(gate, grant, "simulator", str(uuid.uuid4()))


def identity(bound):
    with bound.gate.store.transaction(write=False):
        definition = bound.gate.authority._execution(bound.grant.execution_id)["procedure_id"]
    return {"definition": definition, "procedure": bound.grant.execution_id}


def command(dss, bound):
    return dss.command(
        "CMD1",
        [],
        identity(bound),
        bound.operation,
        lambda: None,
        admission=bound,
    )


def states(gate):
    return gate.db.execute("SELECT stage,state FROM effect_intents ORDER BY rowid").fetchall()


def test_independent_dss_process_five_correlated_receipts_and_no_replay(gate, dss):
    _, _, bound = admission(gate)
    ok, receipts = command(dss, bound)
    assert ok and len(receipts) == 5
    assert states(gate) == [(r["stage"], "ACKED") for r in receipts]
    assert dss.get("state")["core"]["commands_executed"] == 1
    assert (
        gate.db.execute("SELECT provenance FROM effect_intents")
        .fetchone()[0]
        .find(bound.grant.token)
        == -1
    )
    with pytest.raises(UncertainEffect):
        command(dss, bound)
    assert dss.get("state")["core"]["commands_executed"] == 1
    assert states(gate) == [(r["stage"], "ACKED") for r in receipts]


def test_transfer_can_fence_while_receipt_is_pending_without_waiting_for_socket(gate, dss):
    alice, execution, bound = admission(gate)
    bob = Client(gate.authority, "bob")
    claim = bob.claim(execution)

    class Handoff:
        def send(self, stage, connection, packet):
            bound.send(stage, connection, packet)
            if stage == "TRANSPORT":
                # send() has returned, but the driver has not read the receipt yet.
                decision = alice.call("execution.decide", alice.decision(execution, claim))
                assert decision["state"] == "BLOCKED"

        validate = bound.validate
        settle = bound.settle
        uncertain = bound.uncertain

    with pytest.raises(UncertainEffect):
        dss.command(
            "CMD1",
            [],
            identity(bound),
            bound.operation,
            lambda: None,
            admission=Handoff(),
        )
    assert states(gate) == [("TRANSPORT", "ACKED")]
    assert dss.get("state")["core"]["commands_executed"] == 0
    row = gate.authority.list_executions("alice")["executions"][0]
    assert row["owner"] == "alice" and row["epoch"] == 1
    assert row["control_state"] == "RECOVERY_REQUIRED"


def test_live_role_revocation_between_stages_prevents_release(gate, dss):
    _, _, bound = admission(gate)

    class Revoke:
        validate = bound.validate
        send = bound.send
        uncertain = bound.uncertain

        def settle(self, stage, receipt):
            bound.settle(stage, receipt)
            gate.authority.subjects["alice"] = policy({"alice": ["execution:read"]})["alice"]

    with pytest.raises(UncertainEffect):
        dss.command(
            "CMD1",
            [],
            identity(bound),
            bound.operation,
            lambda: None,
            admission=Revoke(),
        )
    assert states(gate) == [("TRANSPORT", "ACKED")]
    assert dss.get("state")["core"]["commands_executed"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("control_epoch", 2),
        ("worker_generation", 2),
        ("worker_incarnation", "other"),
        ("connection_generation", 2),
    ],
)
def test_original_grant_cannot_be_restamped(gate, dss, field, value):
    _, _, bound = admission(gate)
    forged = replace(bound, grant=replace(bound.grant, **{field: value}))
    with pytest.raises(Fault):
        command(dss, forged)
    assert states(gate) == []
    assert dss.get("state")["core"]["commands_executed"] == 0


def test_receipt_capacity_reserved_before_any_wire_effect(gate, dss):
    _, _, bound = admission(gate)
    gate.capacity = 1
    with pytest.raises(UncertainEffect):
        command(dss, bound)
    assert states(gate) == [("TRANSPORT", "ACKED")]
    assert dss.get("state")["core"]["commands_executed"] == 0


def test_wrong_resource_and_endpoint_denied_before_intent(gate, dss):
    _, _, bound = admission(gate)
    wrong = replace(bound, binding="unconfigured")
    with pytest.raises(Fault):
        command(dss, wrong)
    gate.bindings["simulator"] = ("127.0.0.1", 1)
    with pytest.raises(UncertainEffect):
        command(dss, bound)
    assert states(gate) == []


def test_consumed_start_requires_live_start_permission(authority):
    alice = Client(authority, "alice")
    execution = alice.reserve()
    authority.subjects["alice"] = policy({"alice": ["execution:control", "execution:read"]})[
        "alice"
    ]
    with pytest.raises(Fault):
        worker_start(authority, execution)


def test_missing_driver_ledger_commit_retains_hold_and_poison_on_persistence_failure(
    gate, dss, monkeypatch
):
    _, execution, bound = admission(gate)

    @contextmanager
    def broken():
        raise OSError("disk unavailable")
        yield

    monkeypatch.setattr(gate, "_transaction", broken)
    with pytest.raises(UncertainEffect):
        command(dss, bound)
    assert gate.store.failed
    assert dss.get("state")["core"]["commands_executed"] == 0
    assert gate.store.db.execute("SELECT execution_id,state FROM effect_intents").fetchall()[0][
        :
    ] == (execution["id"], "INTENT")


def test_cross_execution_receipt_never_overwrites_other_intent(gate):
    _, _, first = admission(gate, "first")
    _, _, other = admission(gate, "second")
    # Genuine TCP write, with receipt deliberately left unread.
    with socket.create_connection(gate.bindings["simulator"], timeout=2) as connection:
        first.send("TRANSPORT", connection, b"pending")
    with pytest.raises(Fault, match="effect_receipt_fenced"):
        gate.settle(other.grant, first.operation, "TRANSPORT", b"foreign")
    assert states(gate) == [("TRANSPORT", "SENT")]


def test_backpressured_send_is_bounded_and_holds_same_execution_mutex(authority, tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with (
            socket.create_connection(listener.getsockname()) as connection,
            listener.accept()[0] as receiver,
        ):
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
            receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
            connection.setblocking(False)
            while True:
                try:
                    connection.send(b"x" * 65536)
                except BlockingIOError:
                    break
            connection.settimeout(2)
            gate = DriverGate(authority, tmp_path / "driver", {"simulator": listener.getsockname()})
            try:
                _, execution, bound = admission(gate)
                checked, release = threading.Event(), threading.Event()
                original = gate._live
                calls = []

                def live(grant, binding):
                    original(grant, binding)
                    calls.append(True)
                    if len(calls) == 2:
                        checked.set()
                        assert release.wait(2)

                gate._live = live
                failures = []

                def write():
                    try:
                        bound.send("TRANSPORT", connection, b"x" * 65536)
                    except TimeoutError as error:
                        failures.append(error)

                thread = threading.Thread(target=write)
                thread.start()
                assert checked.wait(2)
                # Actual final check is inside the very same mutex used by handoff.
                assert not authority.mutexes[execution["id"]].acquire(blocking=False)
                release.set()
                thread.join(2)
                assert not thread.is_alive() and len(failures) == 1
                assert states(gate) == [("TRANSPORT", "UNCERTAIN")]
                assert connection.gettimeout() == 2
                row = authority.list_executions("alice")["executions"][0]
                assert row["control_state"] == "RECOVERY_REQUIRED"
            finally:
                gate.close()


def test_restart_never_reconciles_pending_write_to_success(tmp_path):
    store = ContextStore(tmp_path / "context", "A")
    service = ExecutionAuthority(store, policy({"alice": PERMISSIONS}), worker_slots=SLOTS)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        gate = DriverGate(service, tmp_path / "driver", {"simulator": listener.getsockname()})
        _, execution, bound = admission(gate)
        with (
            socket.create_connection(listener.getsockname()) as connection,
            listener.accept()[0] as receiver,
        ):
            bound.send("TRANSPORT", connection, b"effect")
            assert receiver.recv(6) == b"effect"
        gate.close()
        store.close()
        store = ContextStore(tmp_path / "context", "A")
        try:
            service = ExecutionAuthority(store, policy({"alice": PERMISSIONS}), worker_slots=SLOTS)
            gate = DriverGate(service, tmp_path / "driver", {"simulator": listener.getsockname()})
            try:
                assert states(gate) == [("TRANSPORT", "UNCERTAIN")]
                row = service.list_executions("alice")["executions"][0]
                assert row["id"] == execution["id"] and row["control_state"] == "RECOVERY_REQUIRED"
                assert store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
            finally:
                gate.close()
        finally:
            store.close()


def test_forged_token_cannot_poison_original_live_execution(gate, dss):
    _, _, bound = admission(gate)
    forged = replace(bound, grant=replace(bound.grant, token="0" * 64))
    with pytest.raises(Fault):
        command(dss, forged)
    assert states(gate) == []
    assert gate.authority.list_executions("alice")["executions"][0]["control_state"] == "OWNED"
    assert command(dss, bound)[0]


def test_operation_uuid_is_bound_across_stages_and_executions(gate):
    _, _, first = admission(gate, "first")
    _, _, second = admission(gate, "second")
    with socket.create_connection(gate.bindings["simulator"], timeout=2) as connection:
        first.send("TRANSPORT", connection, b"pending")
        with pytest.raises(Fault, match="effect_operation_binding_conflict"):
            gate.send(second.grant, "simulator", first.operation, "LOADING", connection, b"other")
    assert states(gate) == [("TRANSPORT", "SENT")]


def test_lost_release_receipt_is_uncertain_and_never_replayed(gate, dss):
    _, _, bound = admission(gate)

    class LoseReceipt:
        def send(self, stage, connection, packet):
            bound.send(stage, connection, packet)
            if stage == "RELEASE":
                connection.close()  # Receipt loss even if bytes already reached the receive buffer.

        validate = bound.validate
        settle = bound.settle
        uncertain = bound.uncertain

    with pytest.raises(UncertainEffect):
        dss.command(
            "CMD1",
            [],
            identity(bound),
            bound.operation,
            lambda: None,
            admission=LoseReceipt(),
        )
    assert states(gate) == [("TRANSPORT", "ACKED"), ("LOADING", "ACKED"), ("RELEASE", "UNCERTAIN")]
    import time

    deadline = time.monotonic() + 2
    while dss.get("state")["core"]["commands_executed"] == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert dss.get("state")["core"]["commands_executed"] == 1
    with pytest.raises(Fault, match="worker_grant_fenced"):
        command(dss, bound)
    assert dss.get("state")["core"]["commands_executed"] == 1


def test_process_death_between_actual_send_and_ledger_commit_retains_uncertainty(tmp_path):
    program = """
import json,os,socket,sys,uuid
from contextlib import contextmanager
from openbexi_spell_server.authority import ExecutionAuthority
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.contracts import policy
from openbexi_spell_server.effects import DriverGate
from test_authority import Client,PERMISSIONS,SLOTS,worker_start
store=ContextStore(sys.argv[1],"A")
authority=ExecutionAuthority(store,policy({"alice":PERMISSIONS}),worker_slots=SLOTS)
endpoint=("127.0.0.1",int(sys.argv[3]))
gate=DriverGate(authority,sys.argv[2],{"simulator":endpoint})
alice=Client(authority,"alice")
execution=alice.reserve()
grant=worker_start(authority,execution)
original=gate._transaction
calls=[]
@contextmanager
def die_before_sent_commit():
 calls.append(True)
 if len(calls)==2:os._exit(71)
 with original() as db:yield db
gate._transaction=die_before_sent_commit
with socket.create_connection(endpoint,timeout=2) as connection:
 gate.send(grant,"simulator",str(uuid.uuid4()),"TRANSPORT",connection,b"effect")
"""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(10)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                program,
                str(tmp_path / "context"),
                str(tmp_path / "driver"),
                str(listener.getsockname()[1]),
            ],
            env=dict(
                os.environ,
                PYTHONPATH=os.pathsep.join([str(ROOT / "server/src"), str(ROOT / "server/tests")]),
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                assert connection.recv(6) == b"effect"
            _, error = child.communicate(timeout=10)
            assert child.returncode == 71, error.decode()
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
        store = ContextStore(tmp_path / "context", "A")
        try:
            service = ExecutionAuthority(store, policy({"alice": PERMISSIONS}), worker_slots=SLOTS)
            gate = DriverGate(service, tmp_path / "driver", {"simulator": listener.getsockname()})
            try:
                assert states(gate) == [("TRANSPORT", "UNCERTAIN")]
                assert (
                    store.db.execute("SELECT state FROM effect_intents").fetchone()[0] == "INTENT"
                )
                assert (
                    service.list_executions("alice")["executions"][0]["control_state"]
                    == "RECOVERY_REQUIRED"
                )
                assert (
                    store.db.execute("SELECT spent FROM workers WHERE slot='slot-0'").fetchone()[0]
                    == 1
                )
            finally:
                gate.close()
        finally:
            store.close()


def test_fenced_adapter_cannot_call_command_without_context_admission(dss):
    with pytest.raises(TypeError, match="admission"):
        dss.command(
            "CMD1",
            [],
            {"definition": "procedure", "procedure": "x"},
            str(uuid.uuid4()),
            lambda: None,
        )


def test_start_permission_revoked_after_grant_blocks_consumption(authority):
    from test_authority import admit_start

    execution = Client(authority, "alice").reserve()
    grant = admit_start(authority, execution)
    authority.subjects["alice"] = policy({"alice": ["execution:read", "execution:control"]})[
        "alice"
    ]
    with pytest.raises(Fault):
        authority.consume_start(grant, grant.worker_slot, grant.worker_incarnation)
    assert authority.store.db.execute("SELECT SUM(spent) FROM workers").fetchone()[0] == 0


def test_receipt_wait_for_one_execution_does_not_block_another(gate, dss):
    from concurrent.futures import ThreadPoolExecutor

    _, _, first = admission(gate, "first")
    _, _, second = admission(gate, "second")
    sent, release = threading.Event(), threading.Event()

    class DelayedReceipt:
        def send(self, stage, connection, packet):
            first.send(stage, connection, packet)
            if stage == "TRANSPORT":
                sent.set()
                assert release.wait(3)

        validate = first.validate
        settle = first.settle
        uncertain = first.uncertain

    with ThreadPoolExecutor(max_workers=2) as pool:
        delayed = pool.submit(
            dss.command,
            "CMD1",
            [],
            identity(first),
            first.operation,
            lambda: None,
            admission=DelayedReceipt(),
        )
        try:
            assert sent.wait(2)
            assert command(dss, second)[0]
            assert not delayed.done()
        finally:
            release.set()
        assert delayed.result(timeout=3)[0]
    assert dss.get("state")["core"]["commands_executed"] == 2


def test_ten_independent_driver_operations_share_no_controller_or_receipt_state(gate, dss):
    from concurrent.futures import ThreadPoolExecutor

    operations = [admission(gate, "procedure-" + str(n))[2] for n in range(10)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda bound: command(dss, bound), operations))
    assert all(ok and len(receipts) == 5 for ok, receipts in results)
    assert dss.get("state")["core"]["commands_executed"] == 10
    assert len(states(gate)) == 50 and all(state == "ACKED" for _, state in states(gate))


@pytest.mark.parametrize("field", ["procedure", "definition", "operation"])
def test_wire_identity_must_match_original_context_binding(gate, dss, field):
    _, _, bound = admission(gate)
    who, operation = identity(bound), bound.operation
    if field == "operation":
        operation = str(uuid.uuid4())
    else:
        who[field] = "another-procedure"
    with pytest.raises(Fault, match="effect_identity_fenced"):
        dss.command("CMD1", [], who, operation, lambda: None, admission=bound)
    assert states(gate) == []
    assert dss.get("state")["core"]["commands_executed"] == 0


@pytest.mark.parametrize("phase", ["intent", "receipt"])
def test_controller_fence_does_not_wait_for_non_effect_ledger_bookkeeping(
    gate, dss, monkeypatch, phase
):
    from concurrent.futures import ThreadPoolExecutor

    alice, execution, bound = admission(gate)
    claim = Client(gate.authority, "bob").claim(execution)
    entered, release = threading.Event(), threading.Event()
    original = gate._transaction
    calls = 0

    @contextmanager
    def delayed_commit():
        nonlocal calls
        calls += 1
        current = calls
        with original() as db:
            yield db
        # Driver INTENT commit precedes send; the third transaction is receipt
        # ACKED. Hold outside the SQL transaction, but inside its driver method.
        if current == (1 if phase == "intent" else 3):
            entered.set()
            assert release.wait(2), "Ledger observation barrier expired"

    monkeypatch.setattr(gate, "_transaction", delayed_commit)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(command, dss, bound)
        try:
            assert entered.wait(2)
            decision = alice.call("execution.decide", alice.decision(execution, claim))
            assert decision["state"] == "BLOCKED"
            assert not pending.done()
        finally:
            release.set()
        with pytest.raises(UncertainEffect):
            pending.result(timeout=3)
    assert dss.get("state")["core"]["commands_executed"] == 0
    expected = "UNCERTAIN" if phase == "intent" else "ACKED"
    for db in (gate.store.db, gate.db):
        assert [tuple(row) for row in db.execute("SELECT stage,state FROM effect_intents")] == [
            ("TRANSPORT", expected)
        ]
    row = gate.authority.list_executions("alice")["executions"][0]
    assert (row["owner"], row["epoch"], row["control_state"]) == ("alice", 1, "RECOVERY_REQUIRED")
    assert gate.store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_concurrent_uncertainty_cannot_overwrite_a_receipt_committed_in_both_ledgers(
    gate, dss, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor

    _, _, bound = admission(gate)
    entered, release = threading.Event(), threading.Event()
    original = gate._transaction
    calls = 0

    @contextmanager
    def delayed_ack():
        nonlocal calls
        calls += 1
        current = calls
        with original() as db:
            yield db
        if current == 3:
            entered.set()
            assert release.wait(2)

    monkeypatch.setattr(gate, "_transaction", delayed_ack)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(command, dss, bound)
        try:
            assert entered.wait(2)
            unknown = pool.submit(gate.uncertain, bound.grant, bound.operation, "TRANSPORT")
        finally:
            release.set()
        unknown.result(timeout=3)
        assert pending.result(timeout=3)[0]
    for db in (gate.store.db, gate.db):
        assert [row[0] for row in db.execute("SELECT state FROM effect_intents")] == ["ACKED"] * 5
    assert gate.authority.list_executions("alice")["executions"][0]["control_state"] == "OWNED"
    assert dss.get("state")["core"]["commands_executed"] == 1


def test_unresolved_receipt_fence_timeout_poison_keeps_authority_closed(gate, dss, monkeypatch):
    _, _, bound = admission(gate)

    @contextmanager
    def cannot_fence(_execution):
        raise Fault(503, "execution_busy")
        yield

    class LostReceipt:
        validate = bound.validate
        send = bound.send
        uncertain = bound.uncertain

        def settle(self, _stage, _receipt):
            monkeypatch.setattr(gate.authority, "_execution_lock", cannot_fence)
            raise TimeoutError("Injected receipt loss with unavailable fencing mutex")

    with pytest.raises(UncertainEffect):
        dss.command(
            "CMD1", [], identity(bound), bound.operation, lambda: None, admission=LostReceipt()
        )
    assert gate.store.failed
    for db in (gate.store.db, gate.db):
        assert [tuple(row) for row in db.execute("SELECT stage,state FROM effect_intents")] == [
            ("TRANSPORT", "SENT")
        ]
    with pytest.raises(Fault) as denied:
        gate.authority.validate_start_grant(bound.grant)
    assert denied.value.code == "state_unavailable"
    assert dss.get("state")["core"]["commands_executed"] == 0
    assert gate.store.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_expired_operation_waiting_for_ledger_writer_cannot_send_late(gate, dss, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import time

    _, _, original = admission(gate)
    bound = replace(original, deadline=time.monotonic() + 0.05)
    entered = threading.Event()
    send = gate.send

    def waiting(*args, **options):
        entered.set()
        return send(*args, **options)

    monkeypatch.setattr(gate, "send", waiting)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with gate.lock:
            pending = pool.submit(command, dss, bound)
            assert entered.wait(2)
            time.sleep(0.1)
        with pytest.raises(UncertainEffect) as denied:
            pending.result(timeout=3)
    assert isinstance(denied.value.__cause__, Fault)
    assert denied.value.__cause__.code == "effect_deadline_expired"
    for db in (gate.store.db, gate.db):
        assert db.execute("SELECT COUNT(*) FROM effect_intents").fetchone()[0] == 0
    assert gate.authority.list_executions("alice")["executions"][0]["control_state"] == "OWNED"
    assert dss.get("state")["core"]["commands_executed"] == 0
