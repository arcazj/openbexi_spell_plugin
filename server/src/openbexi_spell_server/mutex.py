"""Bounded FIFO admission for the Context's short per-execution critical sections.

Repeated checks/stage commits must not barge ahead of already waiting requests.
Timeout is admission failure, never permission to send or replay an operation.
"""

from collections import deque
import threading
import time


class ExecutionMutex:
    CAPACITY = 64  # No more than the internal server's maximum handler bound.

    def __init__(self):
        self.condition = threading.Condition()
        self.waiters: deque[object] = deque()
        self.owner: int | None = None

    def acquire(self, blocking=True, timeout=0.25):
        deadline = time.monotonic() + timeout
        ticket = object()
        with self.condition:
            if not blocking:
                if self.owner is not None or self.waiters:
                    return False
                self.owner = threading.get_ident()
                return True
            if len(self.waiters) >= self.CAPACITY:
                return False
            self.waiters.append(ticket)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.waiters.remove(ticket)
                    self.condition.notify_all()
                    return False
                if self.owner is None and self.waiters[0] is ticket:
                    self.waiters.popleft()
                    self.owner = threading.get_ident()
                    return True
                try:
                    self.condition.wait(remaining)
                except BaseException:
                    self.waiters.remove(ticket)
                    self.condition.notify_all()
                    raise

    def release(self):
        with self.condition:
            if self.owner != threading.get_ident():
                raise RuntimeError("Execution mutex released by a non-owner")
            self.owner = None
            self.condition.notify_all()


class LedgerMutex:
    """Reentrant FIFO writer; SQL/receipt waits never hold the execution mutex.

    The previous RLock had no admission timeout; retain that behavior, with a
    bounded queue and no barging between stages. RPC/write deadlines stay intact.
    """

    CAPACITY = 64

    def __init__(self):
        self.condition = threading.Condition()
        self.waiters: deque[object] = deque()
        self.owner: int | None = None
        self.depth = 0

    def __enter__(self):
        from .contracts import Fault

        actor = threading.get_ident()
        with self.condition:
            if self.owner == actor:
                self.depth += 1
                return self
            if len(self.waiters) >= self.CAPACITY:
                raise Fault(503, "driver_ledger_busy")
            ticket = object()
            self.waiters.append(ticket)
            try:
                while self.owner is not None or self.waiters[0] is not ticket:
                    self.condition.wait()
            except BaseException:
                self.waiters.remove(ticket)
                self.condition.notify_all()
                raise
            self.waiters.popleft()
            self.owner, self.depth = actor, 1
            return self

    def __exit__(self, *_error):
        with self.condition:
            if self.owner != threading.get_ident() or self.depth < 1:
                raise RuntimeError("Ledger mutex released by a non-owner")
            self.depth -= 1
            if not self.depth:
                self.owner = None
                self.condition.notify_all()
