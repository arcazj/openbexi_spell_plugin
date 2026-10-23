"""Single-host worker source preflight client. Never imports or launches native code."""

import argparse
import ctypes
import json
from pathlib import Path
import uuid
import sys

from .contracts import Fault, decode, exact
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
