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
