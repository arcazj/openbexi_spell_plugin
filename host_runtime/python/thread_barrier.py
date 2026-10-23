"""One-shot cooperative background-Python barrier, never whole-family proof.

The private native qualification profile installs this before procedure entry.
CPython monitoring coexists with the original native debugger trace. Only code
in the immutable snapshot is observed; a blocked C extension, unknown/native
thread, child process or native queue is NOT covered. There is no resume route.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path
import socket
import sys
import threading
import time
import uuid


class ThreadBarrier:
    TOOL = 3
    NAME = "openbexi-background-barrier/1"

    def __init__(self, snapshot, entrypoint):
        self.snapshot = Path(snapshot).resolve(strict=True)
        self.entrypoint = Path(entrypoint).resolve(strict=True)
        if not self.snapshot.is_dir() or not self.entrypoint.is_relative_to(
            self.snapshot
        ):
            raise ValueError("Invalid immutable procedure boundary")
        self.condition = threading.Condition()
        self.main = None
        self.participants = {}
        self.code_paths = {}
        self.barrier_id = None
        self.deadline = None
        self.failure = None
        self.expired = False
        self.server = None
        # An occupied monitoring ID is a hard failure, never an invitation to
        # replace another tool or weaken the native debugger.
        sys.monitoring.use_tool_id(self.TOOL, self.NAME)
        try:
            sys.monitoring.register_callback(
                self.TOOL, sys.monitoring.events.LINE, self.line
            )
            sys.monitoring.set_events(self.TOOL, sys.monitoring.events.LINE)
        except BaseException:
            sys.monitoring.register_callback(
                self.TOOL, sys.monitoring.events.LINE, None
            )
            sys.monitoring.free_tool_id(self.TOOL)
            raise

    def line(self, code, _line):
        selected = self.code_paths.get(code)
        if selected is None:
            if len(self.code_paths) >= 2048:
                self.failure = "code_inventory_capacity"
                return
            path = Path(code.co_filename)
            # Synthetic/frozen and relative filenames are not source inventory.
            # Resolving them first would misclassify e.g. <frozen os> whenever
            # the native process cwd is the procedure snapshot.
            selected = path.is_absolute() and path.resolve().is_relative_to(
                self.snapshot
            )
            if not selected:
                return sys.monitoring.DISABLE
            self.code_paths[code] = selected
        if not selected:
            return
        thread = threading.current_thread()
        with self.condition:
            if (
                self.main is None
                and code.co_name == "<module>"
                and Path(code.co_filename) == self.entrypoint
            ):
                self.main = thread
            if thread is self.main:
                return  # Original native controller must pause its own main.
            if thread not in self.participants:
                if len(self.participants) >= 64:
                    self.failure = "participant_capacity"
                    return
                self.participants[thread] = None
                self.condition.notify_all()
            if self.barrier_id is not None:
                self.participants[thread] = self.barrier_id
                self.condition.notify_all()
                # Deadline expiry or control-channel loss NEVER releases a
                # participant. Independent host teardown owns fixture cleanup.
                while True:
                    self.condition.wait()

    def _snapshot(self):
        healthy = (
            sys.monitoring.get_tool(self.TOOL) == self.NAME
            and sys.monitoring.get_events(self.TOOL) == sys.monitoring.events.LINE
        )
        if not healthy:
            self.failure = "monitoring_configuration_changed"
        total = len(self.participants)
        acknowledged = sum(
            value == self.barrier_id and value is not None
            for value in self.participants.values()
        )
        complete = bool(
            healthy
            and self.failure is None
            and not self.expired
            and self.main is not None
            and total > 0
            and total == acknowledged
            and self.barrier_id is not None
        )
        return dict(
            provider=self.NAME,
            barrier_id=self.barrier_id,
            observed_background_threads=total,
            acknowledged_background_threads=acknowledged,
            observed_threads_held=complete,
            main_observed=self.main is not None,
            failure=self.failure,
            deadline_expired=self.expired,
            scope="observed_snapshot_background_python_lines",
            native_main_qualified=False,
            children_qualified=False,
            native_queues_qualified=False,
            quiescence_proven=False,
            effective_transfer=False,
        )

    def pause(self, barrier_id, *, timeout=1.0):
        if type(barrier_id) is not str or str(uuid.UUID(barrier_id)) != barrier_id:
            raise ValueError("Canonical barrier ID required")
        if type(timeout) not in (int, float) or not 0 < timeout <= 3:
            raise ValueError("Bounded cooperative deadline required")
        with self.condition:
            if self.barrier_id is not None and self.barrier_id != barrier_id:
                raise ValueError("Single-use barrier already bound")
            if self.barrier_id is None:
                self.barrier_id = barrier_id
                self.deadline = time.monotonic() + timeout
            # Same-ID replay preserves its original deadline and never resumes.
            while not self._snapshot()["observed_threads_held"]:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0 or self.failure:
                    break
                self.condition.wait(remaining)
            if (
                not self._snapshot()["observed_threads_held"]
                and time.monotonic() >= self.deadline
            ):
                self.expired = True
            return self._snapshot()

    def snapshot_for(self, barrier_id):
        with self.condition:
            if self.barrier_id is None or barrier_id != self.barrier_id:
                raise ValueError("Barrier binding differs")
            return self._snapshot()

    def serve(self, port):
        if self.server is not None:
            raise ValueError("Provider already serving")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Invalid private provider port")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", port))
            listener.listen(4)
        except BaseException:
            listener.close()
            raise
        self.server = listener

        def serve():
            while True:
                stream, peer = listener.accept()
                with stream:
                    stream.settimeout(0.5)
                    try:
                        if peer[0] != "127.0.0.1":
                            raise ValueError("Local peer differs")
                        raw = bytearray()
                        while b"\n" not in raw:
                            chunk = stream.recv(257 - len(raw))
                            if not chunk or len(raw) + len(chunk) > 256:
                                raise ValueError("Provider request exceeds bound")
                            raw.extend(chunk)
                        request = json.loads(raw)
                        if type(request) is not dict or set(request) != {
                            "action",
                            "barrier_id",
                        }:
                            raise ValueError("Provider request differs")
                        if request["action"] == "pause":
                            answer = self.pause(request["barrier_id"])
                        elif request["action"] == "snapshot":
                            answer = self.snapshot_for(request["barrier_id"])
                        else:
                            raise ValueError("Provider operation denied")
                        stream.sendall(json.dumps(answer).encode() + b"\n")
                    except (OSError, ValueError, TypeError):
                        # No request body, process identity or procedure data in
                        # diagnostics. Invalid input cannot remove the barrier.
                        try:
                            stream.sendall(b'{"error":"provider_request_denied"}\n')
                        except OSError:
                            pass

        threading.Thread(target=serve, name="v08-thread-barrier", daemon=True).start()
        return self


def provider_call(port, barrier_id, *, action="pause"):
    """Private diagnostic endpoint. It has no effect/rebind/resume authority."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
        stream.settimeout(2)
        stream.connect(("127.0.0.1", port))
        stream.sendall(
            json.dumps(dict(action=action, barrier_id=barrier_id)).encode() + b"\n"
        )
        raw = bytearray()
        while b"\n" not in raw:
            chunk = stream.recv(2049 - len(raw))
            if not chunk or len(raw) + len(chunk) > 2048:
                raise ValueError("Provider response exceeds bound")
            raw.extend(chunk)
        answer = json.loads(raw)
    if (
        type(answer) is not dict
        or answer.get("provider") != ThreadBarrier.NAME
        or answer.get("barrier_id") != barrier_id
        or answer.get("quiescence_proven") is not False
        or answer.get("effective_transfer") is not False
    ):
        raise ValueError("Provider response binding differs")
    return answer
