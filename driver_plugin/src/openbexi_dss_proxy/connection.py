# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
import uuid
import grpc
from spell.lib.exception import DriverException
from spell.stubs import SPELLDriver_pb2_grpc as stubs

channel = None


def setup():
    global channel
    port = int(os.environ["OPENBEXI_DRIVER_RELAY_PORT"])
    if not 1 <= port <= 65535:
        raise DriverException("Invalid private driver relay port")
    channel = grpc.insecure_channel(
        "127.0.0.1:" + str(port),
        options=[
            ("grpc.enable_retries", 0),
            ("grpc.max_receive_message_length", 65536),
            ("grpc.max_send_message_length", 65536),
        ],
    )
    grpc.channel_ready_future(channel).result(timeout=3)


def close():
    global channel
    if channel:
        channel.close()
        channel = None


def call(family, method, request):
    metadata = ()
    epoch_file = os.environ.get("OPENBEXI_V08_RUNTIME_EPOCH")
    if epoch_file is not None:
        # Capture BEFORE dispatch; a queued call cannot acquire a later owner.
        epoch = Path(epoch_file).read_text()
        if len(epoch) != 36 or str(uuid.UUID(epoch)) != epoch:
            raise DriverException("Native runtime epoch is invalid")
        metadata = (("x-openbexi-runtime-epoch", epoch),)
    if channel is None:
        raise DriverException("Original DSS driver was not initialized")
    try:
        stub = getattr(stubs, "SPELLDriverInterface_" + family + "Stub")(channel)
        return getattr(stub, method)(request, timeout=34, metadata=metadata)
    except grpc.RpcError as error:
        raise DriverException("DSS driver RPC failed", str(error.code())) from error
