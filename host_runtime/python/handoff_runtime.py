"""One-shot in-memory rotation; native requests carry their original epoch tag."""
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
import threading
import uuid

from openbexi_spell_server.contracts import exact, fingerprint
from openbexi_spell_server.launch import start_grant


class HandoffRuntime:
    def __init__(self, request, route, epoch_file):
        self.request, self.route = request, route
        self.path = Path(epoch_file)
        self.lock = threading.RLock()
        self.epoch = request["grant"]["request_id"]
        self.failed = False
        self.rotated = False
        if self.read_epoch() != self.epoch:
            raise ValueError("Initial native runtime epoch differs")

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
            if current == self.epoch:
                return
            if self.rotated:
                raise ValueError("Native runtime already rotated")
            # Do not retry a response-lost activation. The service may have
            # committed new credentials which this process never received.
            self.failed = True
            result = self.route.call(
                {**self.request, "runtime_epoch": current},
                path="/v1/worker/handoff-activate",
                schema="openbexi.worker/2",
            )
            exact(
                result, {"grant", "runtime_capability", "runtime_epoch", "origin_hash"}
            )
            old, new = start_grant(self.request["grant"]), start_grant(result["grant"])
            if (
                result["runtime_epoch"] != current
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
                or new.control_epoch != old.control_epoch + 1
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
