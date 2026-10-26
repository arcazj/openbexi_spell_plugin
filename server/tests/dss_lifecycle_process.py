"""Isolated test DSS: fail only after a real command-stage commit, before ACK.

The production TCP handler, engine, wire packets and SQLite durability are used.
The one-shot fault selector exists only in this test process, never an API route.
"""

import json
import os
import sys
import threading

from dss.engine import DssEngine
from dss.local import LocalRuntime
from dss.server import ApiServer, TcServer


def main():
    path, tcp_port, http_port, selected_stage, mode = sys.argv[1:]
    engine = DssEngine(path)
    runtime = LocalRuntime(engine, bootstrap_servers="unused.local:9092", test_control=True)
    original = engine.consume_transport_fault
    injected = False

    def fault(body, answer):
        nonlocal injected
        result = original(body, answer)
        if mode == "none" or injected or body["stage"] != selected_stage:
            return result
        injected = True
        # process_tc and consume_transport_fault have both committed. The
        # production handler has not encoded or written this receipt yet.
        print(
            json.dumps(dict(event="committed_before_ack", stage=selected_stage, mode=mode)),
            flush=True,
        )
        if mode == "crash":
            os._exit(73)
        if mode == "cut":
            return dict(drop_ack=True, delay_ms=0)
        if mode == "stall":
            return dict(drop_ack=False, delay_ms=2500)
        raise ValueError("Unknown test-only fault selector")

    engine.consume_transport_fault = fault
    tcp = TcServer(("127.0.0.1", int(tcp_port)), runtime)
    runtime.tc_address = tcp.server_address
    http = ApiServer(("127.0.0.1", int(http_port)), runtime)
    threads = [threading.Thread(target=s.serve_forever) for s in (tcp, http)]
    for thread in threads:
        thread.start()
    print(
        json.dumps(
            dict(
                event="ready", pid=os.getpid(), tcp=list(tcp.server_address), http=http.server_port
            )
        ),
        flush=True,
    )
    try:
        sys.stdin.buffer.read(1)
    finally:
        runtime.stop_event.set()
        for server in (http, tcp):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
        engine.close()


if __name__ == "__main__":
    main()
