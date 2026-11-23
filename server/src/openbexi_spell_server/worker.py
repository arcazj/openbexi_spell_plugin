"""Single-host worker source preflight client. Never imports or launches native code."""

import argparse
import ctypes
import json
from pathlib import Path
import time
import uuid
import sys

from .contracts import Fault, decode, exact, fingerprint
from .preflight import canonical_uuid
from .snapshots import verify_directory
from .transport import Route, tls_context


def protect_runtime():
    """Keep the consumption winner's memory private from same-UID procedures.

    No ptrace-policy default is assumed. The worker deployment must also drop
    CAP_SYS_PTRACE (and all other capabilities); a privileged host is trusted.
    Call in the native agent before reading its configuration or spawning code.
    """
    if sys.platform != "linux":
        raise RuntimeError("Native worker memory isolation requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    control = libc.prctl
    control.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    control.restype = ctypes.c_int
    if control(4, 0, 0, 0, 0) != 0 or control(3, 0, 0, 0, 0) != 0:
        raise RuntimeError("Native worker memory isolation unavailable")


def preflight(config, *, details=False):
    exact(
        config,
        {
            "ca",
            "certificate",
            "key",
            "context_url",
            "context_fingerprint",
            "context_id",
            "execution_id",
            "worker_slot",
            "worker_incarnation",
            "snapshot_directory",
        },
    )
    tls = tls_context(config["ca"], config["certificate"], config["key"])
    route = Route(config["context_url"], config["context_fingerprint"], tls)
    scope = dict(
        schema="openbexi.worker/1",
        context_id=config["context_id"],
        execution_id=config["execution_id"],
    )
    challenge = route.call(
        {**scope, "request_id": str(uuid.uuid4())},
        path="/v1/worker/challenge",
        schema="openbexi.worker/1",
    )
    exact(
        challenge,
        {"challenge_id", "expires_at", "binding", "manifest", "source_sha256", "runtime_enabled"},
    )
    binding = challenge["binding"]
    if (
        type(binding) is not dict
        or binding.get("execution_id") != config["execution_id"]
        or binding.get("worker_slot") != config["worker_slot"]
        or binding.get("worker_incarnation") != config["worker_incarnation"]
        or challenge["runtime_enabled"] is not False
    ):
        raise Fault(403, "worker_assignment_mismatch")
    observed = verify_directory(config["snapshot_directory"], challenge["manifest"])
    if observed != challenge["source_sha256"]:
        raise Fault(403, "source_inventory_mismatch")
    receipt = route.call(
        {**scope, "challenge_id": challenge["challenge_id"], "source_sha256": observed},
        path="/v1/worker/verify",
        schema="openbexi.worker/1",
    )
    exact(receipt, {"verified", "execution_id", "source_sha256", "runtime_enabled"})
    if (
        receipt["verified"] is not True
        or receipt["runtime_enabled"] is not False
        or receipt["execution_id"] != config["execution_id"]
        or receipt["source_sha256"] != observed
    ):
        raise Fault(403, "worker_receipt_mismatch")
    return (receipt, challenge) if details else receipt


def wait_for_assignment(config, readonly_tree):
    """Poll a fixed Context as one static worker, then accept one private delivery."""
    fields = {
        "ca",
        "certificate",
        "key",
        "context_url",
        "context_fingerprint",
        "context_id",
        "worker_slot",
        "worker_incarnation",
    }
    exact(config, fields | {"runtime_image", "snapshots"})
    image = config["runtime_image"]
    if not isinstance(image, str) or not image.startswith("sha256:"):
        raise ValueError("An exact native worker image is required")
    fingerprint(image[7:])
    snapshots = config["snapshots"]
    if type(snapshots) is not dict or not 1 <= len(snapshots) <= 64:
        raise ValueError("One to 64 immutable source mounts are required")
    for checksum, directory in snapshots.items():
        fingerprint(checksum)
        if not isinstance(directory, str) or not Path(directory).is_absolute():
            raise ValueError("A configured absolute source mount is required")
    route = Route(
        config["context_url"],
        config["context_fingerprint"],
        tls_context(config["ca"], config["certificate"], config["key"]),
    )
    schema = "openbexi.worker-assignment/1"
    scope = {"schema": schema, "context_id": config["context_id"]}
    previous = None
    while True:
        reply = route.call(scope, path="/v1/worker/assignment", schema=schema)
        assignment = exact(reply, {"assignment"})["assignment"]
        if assignment is None or assignment == previous:
            time.sleep(0.25)
            continue
        exact(assignment, {"execution_id", "preparation_id", "source_sha256", "runtime_image"})
        execution_id = canonical_uuid(assignment["execution_id"])
        preparation_id = canonical_uuid(assignment["preparation_id"])
        checksum = fingerprint(assignment["source_sha256"])
        if assignment["runtime_image"] != image or checksum not in snapshots:
            raise Fault(403, "worker_image_or_snapshot_unavailable")
        worker = {name: config[name] for name in fields}
        worker.update(execution_id=execution_id, snapshot_directory=snapshots[checksum])
        readonly_tree(worker["snapshot_directory"])
        verified = preflight(worker, details=True)
        if verified[0]["source_sha256"] != checksum:
            raise Fault(403, "worker_assignment_source_mismatch")
        previous = assignment
        # Only an explicit empty delivery permits another poll. Lost transport
        # or acceptance receipts terminate this worker without a fresh attempt.
        until = time.monotonic() + 25
        delivery = {**scope, "execution_id": execution_id, "preparation_id": preparation_id}
        while time.monotonic() < until:
            reply = route.call(delivery, path="/v1/worker/start-delivery", schema=schema)
            grant = exact(reply, {"grant"})["grant"]
            if grant is not None:
                return worker, grant, verified
            time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = preflight(decode(args.config.read_bytes()))
    except (Fault, OSError) as error:
        result = dict(
            verified=False,
            runtime_enabled=False,
            error=error.code if isinstance(error, Fault) else "worker_preflight_unavailable",
        )
    print(json.dumps(result), flush=True)
    return 0 if result.get("verified") is True and result.get("runtime_enabled") is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
