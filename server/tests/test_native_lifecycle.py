"""A FINISHED status cannot authorize teardown before durable lifecycle audit."""

import ast
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
import time

import pytest

from test_child_gate import module


def acknowledge(audit, member, phase):
    audit.acknowledge(f"Procedure {phase}: {member} at original timestamp", [member])


def test_delayed_original_finish_receipt_keeps_worker_and_relay_alive():
    audit = module.NativeLifecycleReceipts()
    acknowledge(audit, "root#1", "started")
    waiting, returned = Event(), Event()

    def complete():
        audit.wait(lambda: ["root#1"], waiting.set, timeout=1)
        returned.set()

    thread = Thread(target=complete)
    thread.start()
    try:
        assert waiting.wait(0.5)
        assert not returned.wait(0.05)
        acknowledge(audit, "root#1", "finished")
        assert returned.wait(0.5)
    finally:
        thread.join(timeout=2)
        assert not thread.is_alive()


@pytest.mark.parametrize("prompt_probe", [False, True])
def test_actual_worker_completion_waits_before_announcing_finished_or_cleanup(prompt_probe):
    source = Path(__file__).resolve().parents[2] / "host_runtime/python/v08_worker.py"
    tree = ast.parse(source.read_text())

    def finished(node):
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "emit"
            and node.value.args
            and isinstance(node.value.args[0], ast.Constant)
            and node.value.args[0].value == "native-finished"
        )

    block = next(n for n in ast.walk(tree) if isinstance(n, ast.Try) and any(map(finished, n.body)))
    end = next(i for i, node in enumerate(block.body) if finished(node))
    start = max(i for i, node in enumerate(block.body[:end]) if isinstance(node, ast.While)) + 1
    code = compile(
        ast.Module(body=block.body[start : end + 1], type_ignores=[]), str(source), "exec"
    )
    audit = module.NativeLifecycleReceipts()
    acknowledge(audit, "root#1", "started")
    waiting, announced = Event(), Event()
    observed, inspected = Event(), Event()

    def emit(kind, **_fields):
        if kind == "native-prompt-terminal-observed":
            observed.set()
        elif kind == "native-finished":
            announced.set()

    namespace = dict(
        prompt_probe=prompt_probe,
        Path=lambda _path: SimpleNamespace(is_file=inspected.is_set),
        time=time,
        state="FINISHED",
        lifecycle=audit,
        child_gate=SimpleNamespace(started={"root#1": None}),
        pump=waiting.set,
        denied=set(),
        emit=emit,
        grant=SimpleNamespace(execution_id="original-execution"),
        driver_methods=set(),
        count=0,
    )
    thread = Thread(target=lambda: exec(code, namespace))
    thread.start()
    try:
        assert waiting.wait(0.5)
        assert not announced.wait(0.05)
        acknowledge(audit, "root#1", "finished")
        if prompt_probe:
            assert observed.wait(0.5)
            assert not announced.wait(0.05)
            inspected.set()
        assert announced.wait(0.5)
    finally:
        inspected.set()
        thread.join(timeout=6)
        assert not thread.is_alive()


def test_every_admitted_child_needs_its_own_original_durable_finish():
    audit = module.NativeLifecycleReceipts()
    for member in ("root#1", "child#0", "grand#0"):
        acknowledge(audit, member, "started")
    for member in ("root#1", "child#0"):
        acknowledge(audit, member, "finished")
    with pytest.raises(TimeoutError, match="audit did not settle"):
        audit.wait(lambda: ["root#1", "child#0", "grand#0"], lambda: None, timeout=0.03)
    acknowledge(audit, "grand#0", "finished")
    audit.wait(lambda: ["root#1", "child#0", "grand#0"], lambda: None, timeout=0)


def test_foreign_or_ordinary_event_cannot_substitute_for_missing_receipt():
    audit = module.NativeLifecycleReceipts()
    for message in (
        "Procedure finished: stolen#0 at timestamp",
        "Procedure finished: root#10 at timestamp",
        "ordinary procedure output",
    ):
        audit.acknowledge(message, ["root#1"])
    assert audit.counts == {}
    with pytest.raises(TimeoutError):
        audit.wait(lambda: ["root#1"], lambda: None, timeout=0)


def test_duplicate_receipts_fail_closed_and_never_become_a_success():
    audit = module.NativeLifecycleReceipts()
    acknowledge(audit, "root#1", "started")
    acknowledge(audit, "root#1", "finished")
    with pytest.raises(ValueError, match="Duplicate"):
        acknowledge(audit, "root#1", "finished")
    with pytest.raises(ValueError, match="invalid"):
        audit.wait(lambda: ["root#1"], lambda: None)


@pytest.mark.parametrize("members", [[], [str(n) for n in range(66)]])
def test_empty_or_unbounded_participants_cannot_pass(members):
    with pytest.raises(ValueError, match="member bound"):
        module.NativeLifecycleReceipts().wait(lambda: members, lambda: None)


def test_per_context_receipt_memory_is_bounded_and_not_reusable():
    audit = module.NativeLifecycleReceipts()
    for n in range(65):
        for phase in ("started", "finished"):
            acknowledge(audit, f"member#{n}", phase)
    assert len(audit.counts) == 130
    with pytest.raises(ValueError, match="capacity"):
        acknowledge(audit, "member#65", "started")
    assert len(audit.counts) == 130
