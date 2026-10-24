"""Real contending threads: no barging, bounded wait, cancelled-head progress."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from openbexi_spell_server.mutex import ExecutionMutex


def queued(mutex, count):
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        with mutex.condition:
            if len(mutex.waiters) == count:
                return
        threading.Event().wait(0.001)
    raise AssertionError("Contender did not reach execution admission")


def test_holder_cannot_barge_ahead_of_already_waiting_requests():
    mutex, order = ExecutionMutex(), []
    assert mutex.acquire(timeout=1)

    def waiter(number):
        assert mutex.acquire(timeout=2)
        try:
            order.append(number)
        finally:
            mutex.release()

    with ThreadPoolExecutor(max_workers=10) as pool:
        pending = []
        for number in range(10):
            pending.append(pool.submit(waiter, number))
            queued(mutex, number + 1)
        mutex.release()
        # Immediate reacquisition must join the tail, even when the releasing
        # thread remains scheduled and can perform more work without waiting.
        assert mutex.acquire(timeout=2)
        try:
            order.append("holder")
        finally:
            mutex.release()
        for task in pending:
            task.result(timeout=2)
    assert order == [*range(10), "holder"]


def test_expired_head_cannot_block_next_waiter_or_be_granted_late():
    mutex = ExecutionMutex()
    assert mutex.acquire(timeout=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        expired = pool.submit(mutex.acquire, timeout=0.02)
        queued(mutex, 1)
        assert expired.result(timeout=1) is False

        def next_waiter():
            assert mutex.acquire(timeout=1)
            mutex.release()

        next_task = pool.submit(next_waiter)
        queued(mutex, 1)
        mutex.release()
        next_task.result(timeout=1)
    assert mutex.acquire(blocking=False)
    mutex.release()


def test_waiter_capacity_denies_without_entering_or_displacing_the_queue(monkeypatch):
    mutex = ExecutionMutex()
    monkeypatch.setattr(mutex, "CAPACITY", 2)
    assert mutex.acquire(timeout=1)

    def waiter():
        assert mutex.acquire(timeout=1)
        mutex.release()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(waiter)
        queued(mutex, 1)
        second = pool.submit(waiter)
        queued(mutex, 2)
        assert not mutex.acquire(timeout=1)
        assert not mutex.acquire(blocking=False)
        mutex.release()
        first.result(timeout=1)
        second.result(timeout=1)


def test_non_owner_release_cannot_remove_another_requests_fence():
    mutex = ExecutionMutex()
    assert mutex.acquire(timeout=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match="non-owner"):
            pool.submit(mutex.release).result(timeout=1)
    assert not mutex.acquire(blocking=False)
    mutex.release()


def test_interrupted_wait_removes_its_ticket_without_releasing_the_owner(monkeypatch):
    mutex = ExecutionMutex()
    assert mutex.acquire(timeout=1)

    def interrupted(_timeout):
        raise InterruptedError("Injected cancelled waiter")

    monkeypatch.setattr(mutex.condition, "wait", interrupted)
    with pytest.raises(InterruptedError):
        mutex.acquire(timeout=1)
    assert not mutex.acquire(blocking=False)
    mutex.release()
    assert mutex.acquire(blocking=False)
    mutex.release()


def test_ledger_writer_is_reentrant_and_new_stages_cannot_barge():
    from openbexi_spell_server.mutex import LedgerMutex

    mutex, order = LedgerMutex(), []

    def waiter(number):
        with mutex:
            order.append(number)
            with mutex:
                assert mutex.depth == 2

    with ThreadPoolExecutor(max_workers=10) as pool:
        mutex.__enter__()
        try:
            pending = []
            for number in range(10):
                pending.append(pool.submit(waiter, number))
                queued(mutex, number + 1)
            with mutex:
                assert mutex.depth == 2
        finally:
            mutex.__exit__()
        with mutex:
            order.append("next-stage")
        for task in pending:
            task.result(timeout=2)
    assert order == [*range(10), "next-stage"]
    assert mutex.owner is None and mutex.depth == 0


def test_ledger_writer_capacity_never_displaces_original_waiter(monkeypatch):
    from openbexi_spell_server.contracts import Fault
    from openbexi_spell_server.mutex import LedgerMutex

    mutex = LedgerMutex()
    monkeypatch.setattr(mutex, "CAPACITY", 1)

    def waiter():
        with mutex:
            return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        mutex.__enter__()
        try:
            original = pool.submit(waiter)
            queued(mutex, 1)
            with pytest.raises(Fault) as full:
                pool.submit(waiter).result(timeout=1)
            assert full.value.code == "driver_ledger_busy"
        finally:
            mutex.__exit__()
        assert original.result(timeout=1)
    assert not mutex.waiters


def test_interrupted_ledger_wait_removes_ticket_without_unlocking_owner(monkeypatch):
    from openbexi_spell_server.mutex import LedgerMutex

    mutex = LedgerMutex()
    original = mutex.condition.wait

    def interrupted():
        raise InterruptedError("Injected interrupted ledger waiter")

    def contender():
        with mutex:
            raise AssertionError("Interrupted waiter entered")

    with mutex:
        monkeypatch.setattr(mutex.condition, "wait", interrupted)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(InterruptedError):
                pool.submit(contender).result(timeout=1)
            with pytest.raises(RuntimeError, match="non-owner"):
                pool.submit(mutex.__exit__).result(timeout=1)
        assert not mutex.waiters and mutex.depth == 1
        monkeypatch.setattr(mutex.condition, "wait", original)
    with mutex:
        assert mutex.depth == 1
