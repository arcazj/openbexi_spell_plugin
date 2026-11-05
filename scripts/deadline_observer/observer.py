"""Diagnostic wrappers. Preserve calls, exceptions, locking and durability.

PYTEST_DONT_REWRITE

Records are buffered until process exit; no observer writes run inside measured
Python critical sections. SQL values, credentials and request bodies are omitted.
Durations nest and overlap: they must never be summed across categories.
"""

import atexit
import functools
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

EVENTS = []
LOCAL = threading.local()
PHASE = "startup"
INSTALLED = False


def emit(kind, label, started, **fields):
    EVENTS.append(
        dict(
            kind=kind,
            label=label,
            start_ns=started,
            duration_ns=time.monotonic_ns() - started,
            pid=os.getpid(),
            tid=threading.get_native_id(),
            phase=PHASE,
            operation=getattr(LOCAL, "operation", None),
            **fields,
        )
    )


def timed(cls, name, label=None, operation_index=None):
    original = getattr(cls, name)

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        previous = getattr(LOCAL, "operation", None)
        if operation_index is not None:
            LOCAL.operation = args[operation_index]
        started = time.monotonic_ns()
        error = None
        try:
            return original(*args, **kwargs)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            emit("span", label or cls.__name__ + "." + name, started, error=error)
            LOCAL.operation = previous

    setattr(cls, name, wrapped)


class Lock:
    def __init__(self, original, label):
        self.original, self.label = original, label

    def acquire(self, *args, **kwargs):
        started = time.monotonic_ns()
        result = self.original.acquire(*args, **kwargs)
        emit("lock_wait", self.label, started, acquired=bool(result))
        return result

    def release(self):
        return self.original.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

    def __getattr__(self, name):
        return getattr(self.original, name)


def observe_lock(cls, attribute, label):
    original = cls.__init__

    @functools.wraps(original)
    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        setattr(self, attribute, Lock(getattr(self, attribute), label))

    cls.__init__ = init


class Connection(sqlite3.Connection):
    def execute(self, sql, *args, **kwargs):
        started = time.monotonic_ns()
        error = None
        try:
            return super().execute(sql, *args, **kwargs)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            emit(
                "sqlite",
                getattr(self, "trace_label", "initializing"),
                started,
                statement=sql.split()[0].upper() if sql.strip() else "EMPTY",
                error=error,
            )


def dump():
    target = Path(os.environ["OPENBEXI_DEADLINE_TRACE"])
    target.mkdir(parents=True, exist_ok=True)
    with (target / ("python-" + str(os.getpid()) + ".jsonl")).open("x") as stream:
        for event in EVENTS:
            stream.write(json.dumps(event) + "\n")


def install():
    global INSTALLED
    if INSTALLED:
        return
    INSTALLED = True
    root = Path(os.environ["OPENBEXI_DEADLINE_ROOT"])
    sys.path[:0] = [
        str(root / path) for path in ("server/src", "src", "driver_plugin/src")
    ]
    connect = sqlite3.connect

    def observed_connect(database, *args, **kwargs):
        if "factory" not in kwargs:
            kwargs["factory"] = Connection
        result = connect(database, *args, **kwargs)
        if isinstance(result, Connection):
            result.trace_label = str(database)
        return result

    sqlite3.connect = observed_connect
    popen = subprocess.Popen

    class Popen(popen):
        def __init__(self, *args, **kwargs):
            # The original DSS fixture deliberately supplies its own PYTHONPATH.
            # Add only this observer to that path, keeping every fixture argument.
            if kwargs.get("env") is not None:
                env = dict(kwargs["env"])
                env["PYTHONPATH"] = (
                    str(Path(__file__).parent) + os.pathsep + env.get("PYTHONPATH", "")
                )
                kwargs["env"] = env
            super().__init__(*args, **kwargs)

    subprocess.Popen = Popen
    from openbexi_spell_server.store import ContextStore
    from openbexi_spell_server.mutex import ExecutionMutex, LedgerMutex
    from openbexi_spell_server.effects import DriverGate
    from openbexi_spell_server.liveness import ControllerLiveness
    from openbexi_spell_dss.context_driver import ContextDriver
    from openbexi_spell_dss.fenced_transport import Transport, CommandTiming
    from dss.engine import DssEngine

    observe_lock(ContextStore, "lock", "ContextStore.lock")
    observe_lock(DssEngine, "_lock", "DssEngine.lock")
    timed(ExecutionMutex, "acquire", "ExecutionMutex.wait")
    timed(LedgerMutex, "__enter__", "LedgerMutex.wait")
    timed(DriverGate, "send", operation_index=3)
    timed(DriverGate, "settle", operation_index=2)
    timed(ContextDriver, "dispatch", operation_index=2)
    timed(Transport, "get")
    timed(Transport, "command", operation_index=4)
    timed(ControllerLiveness, "heartbeat")
    measure = CommandTiming.measure
    from contextlib import contextmanager

    @contextmanager
    def measured(self, phase, stage=None):
        started = time.monotonic_ns()
        try:
            with measure(self, phase, stage):
                yield
        finally:
            emit("rpc_phase", phase, started, stage=stage)

    CommandTiming.measure = measured
    atexit.register(dump)
    emit(
        "observer",
        "installed",
        time.monotonic_ns(),
        python=sys.version,
        sqlite=sqlite3.sqlite_version,
    )


def pytest_runtest_logstart(nodeid, location):
    emit("test", nodeid, time.monotonic_ns())


def pytest_collection_modifyitems(items):
    module = sys.modules.get("test_native_driver")
    if module is not None:
        timed(module, "native_call", "client.native_call")


def pytest_runtest_setup(item):
    global PHASE
    PHASE = "setup"


def pytest_runtest_call(item):
    global PHASE
    PHASE = "call"


def pytest_runtest_teardown(item):
    global PHASE
    PHASE = "teardown"


def pytest_runtest_logreport(report):
    emit(
        "outcome",
        report.nodeid,
        time.monotonic_ns(),
        when=report.when,
        outcome=report.outcome,
        reported_duration=report.duration,
    )
