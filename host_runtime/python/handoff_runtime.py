"""One delivery per transfer; native requests carry their original epoch tag."""
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from contextlib import contextmanager
import threading
import time
import uuid

from openbexi_spell_server.contracts import exact, fingerprint
from openbexi_spell_server.launch import start_grant
from openbexi_spell_server.family import FamilyAdmission


class HandoffRuntime:
    def __init__(self, request, route, epoch_file):
        self.request, self.route = request, route
        self.path = Path(epoch_file)
        self.lock = threading.RLock()
        self.idle = threading.Condition(self.lock)
        self.active_calls = 0
        self.draining = False
        self.prepare_path = self.path.with_name("handoff-prepare")
        self.epoch = request["grant"]["request_id"]
        self.failed = False
        self.rotated = False
        self.rotations = 0
        self.seen_epochs = {self.epoch}
        self.origin = FamilyAdmission.origin(start_grant(request["grant"]))
        if self.read_epoch() != self.epoch:
            raise ValueError("Initial native runtime epoch differs")

    @contextmanager
    def outbound(self):
        """Drain existing RPCs before host freeze; never retry a lost reply."""
        with self.idle:
            if self.draining or self.failed:
                raise ValueError("Native transport is held for host handoff")
            self.active_calls += 1
        try:
            yield
        finally:
            with self.idle:
                self.active_calls -= 1
                self.idle.notify_all()

    def checkpoint(self, emit):
        """Park only the agent loop. This is NOT proof of family quiescence.

        The separate host still proves cgroup freeze, process identity and
        settled journals. This prevents that freeze from suspending a TLS
        exchange or a native status query halfway through its deadline.
        Only a different epoch AND the original one-shot activation receipt
        can leave this hold; removing the prepare marker cannot resume it.
        """
        try:
            prepared = self.prepare_path.read_text()
        except FileNotFoundError:
            return
        with self.idle:
            if prepared != self.epoch:
                if prepared in self.seen_epochs:
                    return  # Previously completed request, never a new drain.
                raise ValueError("Host handoff prepare identity differs")
            self.draining = True
            while self.active_calls:
                self.idle.wait(timeout=0.1)
            previous = self.epoch
        emit(
            "native-handoff-agent-drained",
            runtime_epoch=previous,
            active_calls=0,
            quiescence_proven=False,
        )
        while self.read_epoch() == previous:
            time.sleep(0.02)
        # Bypass the held outbound wrapper ONLY for this one-shot activation.
        # A lost response leaves failed/draining set; no poll or retry escapes.
        with self.idle:
            self.ensure()
            self.draining = False
            self.idle.notify_all()

    def guarded_route(self):
        runtime = self

        class GuardedRoute:
            def call(self, *args, **kwargs):
                with runtime.outbound():
                    return runtime.route.call(*args, **kwargs)

        return GuardedRoute()

    def read_epoch(self):
        value = self.path.read_text()
        if len(value) != 36 or str(uuid.UUID(value)) != value:
            raise ValueError("Native runtime epoch is invalid")
        return value

    def ensure(self, captured=None, *, native=False):
        with self.lock:
            if self.failed:
                raise ValueError("Native runtime rotation is uncertain")
            current = self.read_epoch()
            if native and captured != current:
                raise ValueError("Original native operation epoch is fenced")
            if native and self.draining:
                raise ValueError("Native transport is held for host handoff")
            if current == self.epoch:
                return
            if current in self.seen_epochs or self.rotations >= 8:
                self.failed = True
                raise ValueError(
                    "Native runtime epoch replay or rotation capacity reached"
                )
            # Do not retry a response-lost activation. The service may have
            # committed new credentials which this process never received.
            self.failed = True
            result = self.route.call(
                {**self.request, "runtime_epoch": current},
                path="/v1/worker/handoff-activate",
                schema="openbexi.worker/2",
            )
            exact(
                result,
                {
                    "grant",
                    "runtime_capability",
                    "runtime_epoch",
                    "origin_hash",
                    "activation_kind",
                },
            )
            old, new = start_grant(self.request["grant"]), start_grant(result["grant"])
            if (
                result["runtime_epoch"] != current
                or result["origin_hash"] != self.origin
                or any(
                    getattr(old, k) != getattr(new, k)
                    for k in (
                        "authority_incarnation",
                        "execution_id",
                        "worker_slot",
                        "worker_incarnation",
                        "worker_generation",
                        "operation_digest",
                    )
                )
                or result["activation_kind"] not in {"transfer", "rebind"}
                or new.control_epoch
                != old.control_epoch + (result["activation_kind"] == "transfer")
                or (
                    result["activation_kind"] == "rebind"
                    and new.connection_id == old.connection_id
                )
                or new.connection_generation != old.connection_generation + 1
                or new.request_id == old.request_id
                or new.token == old.token
            ):
                raise ValueError("Rotated runtime receipt differs")
            fingerprint(result["runtime_capability"])
            fingerprint(result["origin_hash"])
            self.request.update(
                grant=result["grant"], runtime_capability=result["runtime_capability"]
            )
            self.epoch, self.rotated, self.failed = current, True, False
            self.rotations += 1
            self.seen_epochs.add(current)
