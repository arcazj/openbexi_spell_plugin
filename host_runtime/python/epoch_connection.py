"""Trusted opt-in bootstrap for the frozen driver's original gRPC channel.

Loaded by the candidate Executor before driver initialization, including when
CPython is isolated. Preserve the installed command scheduler and RPC budgets.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import namedtuple
from pathlib import Path
import os
import uuid

HEADER = "x-openbexi-runtime-epoch"


def capture_metadata(metadata, path):
    # Explicitly captured packets retain their original tag, including stale or
    # duplicate tags. The private relay rejects those; never restamp old work.
    metadata = tuple(metadata or ())
    if any(key == HEADER for key, _ in metadata):
        return metadata
    epoch = Path(path).read_text()
    if len(epoch) != 36 or str(uuid.UUID(epoch)) != epoch:
        raise ValueError("Native runtime epoch is invalid")
    return (*metadata, (HEADER, epoch))


def install():
    import grpc
    from openbexi_dss_proxy import connection

    path = os.environ["OPENBEXI_V08_RUNTIME_EPOCH"]
    if path != "/control/handoff-epoch" or connection.channel is not None:
        raise RuntimeError("Native epoch bootstrap must precede driver setup")
    capture_metadata(None, path)
    original_setup = connection.setup

    class Details(
        namedtuple(
            "Details", "method timeout metadata credentials wait_for_ready compression"
        ),
        grpc.ClientCallDetails,
    ):
        pass

    class Epoch(grpc.UnaryUnaryClientInterceptor):
        def intercept_unary_unary(self, continuation, details, request):
            captured = Details(
                details.method,
                details.timeout,
                capture_metadata(details.metadata, path),
                details.credentials,
                details.wait_for_ready,
                details.compression,
            )
            return continuation(captured, request)

    def setup():
        original_setup()
        connection.channel = grpc.intercept_channel(connection.channel, Epoch())

    connection.setup = setup
