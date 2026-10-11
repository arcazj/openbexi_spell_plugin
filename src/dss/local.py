"""Deterministic loopback DSS fixture using the existing binary TC server/engine."""
from __future__ import annotations

import argparse
from pathlib import Path
import threading

from .engine import DssEngine
from .server import ApiServer, DssRuntime, TcServer


class LocalRuntime(DssRuntime):
    manual_clock = True
    def health(self):
        return {'status': 'ready', 'profile': 'deterministic-local-test',
                'transport': 'HTTP and binary TCP', 'automatic_clock': False,
                'kafka_publisher': False, 'outbox': self.engine.outbox_status()}


def create_servers(path, port=8085):
    engine = DssEngine(path)
    runtime = LocalRuntime(engine, bootstrap_servers='unused.local:9092', test_control=True)
    tcp = None
    try:
        tcp = TcServer(('127.0.0.1', 0), runtime)
        runtime.tc_address = tcp.server_address
        api = ApiServer(('127.0.0.1', port), runtime)
        return runtime, tcp, api
    except BaseException:
        if tcp:
            tcp.server_close()
        engine.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8085)
    parser.add_argument('--database', type=Path, default=Path('var/dss.sqlite'))
    args = parser.parse_args(argv)
    runtime, tcp, api = create_servers(args.database, args.port)
    thread = threading.Thread(target=tcp.serve_forever, daemon=True)
    thread.start()
    print(f'DSS ready: http://127.0.0.1:{api.server_port}/api/v1/state', flush=True)
    print('Local synthetic data; manual clock. Kafka profile is optional and separate.', flush=True)
    try:
        api.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop_event.set()
        tcp.shutdown()
        tcp.server_close()
        api.server_close()
        thread.join(timeout=5)
        runtime.engine.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
