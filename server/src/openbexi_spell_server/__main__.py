"""Explicit internal services and an opt-in retained worker launch profile."""

import argparse
import json
import signal
import threading
from pathlib import Path

from .contracts import MAX_BODY, decode, exact
from .services import Context, Listener
from .gateway import Gateway
from .store import ContextStore
from .transport import Route, Server, tls_context


def main(*, driver_factory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("listener", "context", "gateway"))
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = decode(args.config.read_bytes())
    common = {"ca", "certificate", "key", "bind", "port", "allowed_hosts", "max_handlers"}
    specific = (
        {"context_id", "state_directory", "listener_fingerprint", "subjects"}
        if args.role == "context"
        else (
            {"listener_url", "listener_fingerprint", "clients"}
            if args.role == "gateway"
            else {"edge_fingerprint", "identities", "scopes", "contexts"}
        )
    )
    optional = (
        {
            "worker_slots",
            "approved_sources",
            "worker_credentials",
            "worker_launch",
            "native_pause",
            "native_children",
            "native_controls",
            "native_commands",
        }
        if args.role == "context"
        else set()
    )
    if args.role == "context" and driver_factory is not None:
        optional.add("native_driver")
    if (
        type(config) is not dict
        or not common | specific <= set(config)
        or not set(config) <= common | specific | optional
    ):
        parser.error("Invalid configuration fields")
    if (
        not isinstance(config["bind"], str)
        or type(config["port"]) is not int
        or not 0 <= config["port"] <= 65535
        or type(config["allowed_hosts"]) is not list
        or any(not isinstance(host, str) for host in config["allowed_hosts"])
    ):
        parser.error("Invalid bind/host configuration")
    server_tls = tls_context(config["ca"], config["certificate"], config["key"], server=True)
    store = None
    app: Context | Listener | Gateway | None = None
    try:
        if args.role == "context":
            store = ContextStore(config["state_directory"], config["context_id"])
            app = Context(
                store,
                config["listener_fingerprint"],
                config["subjects"],
                worker_slots=config.get("worker_slots"),
                approved_sources=config.get("approved_sources"),
                worker_credentials=config.get("worker_credentials"),
                worker_launch=config.get("worker_launch"),
                native_pause=config.get("native_pause"),
                native_children=config.get("native_children"),
                native_controls=config.get("native_controls"),
                native_commands=config.get("native_commands"),
                native_driver_factory=(
                    lambda authority: driver_factory(authority, config["native_driver"])
                )
                if driver_factory is not None and "native_driver" in config
                else None,
            )
        elif args.role == "gateway":
            app = Gateway(
                config["listener_url"],
                config["listener_fingerprint"],
                tls_context(config["ca"], config["certificate"], config["key"]),
                config["clients"],
            )
        else:
            client_tls = tls_context(config["ca"], config["certificate"], config["key"])
            routes = {}
            for name, target in config["contexts"].items():
                exact(target, {"url", "fingerprint"})
                routes[name] = Route(target["url"], target["fingerprint"], client_tls)
            app = Listener(
                config["edge_fingerprint"], config["identities"], config["scopes"], routes
            )
        server = Server(
            (config["bind"], config["port"]),
            app,
            server_tls,
            allowed_hosts=config["allowed_hosts"],
            max_handlers=config["max_handlers"],
        )
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(
                sig, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start()
            )
        print(
            json.dumps(
                dict(
                    role=args.role,
                    port=server.server_port,
                    runtime_enabled=False,
                    max_body=MAX_BODY,
                )
            ),
            flush=True,
        )
        try:
            server.serve_forever(poll_interval=0.05)
        finally:
            server.server_close()
    finally:
        try:
            if isinstance(app, Context):
                app.close()
        finally:
            if store:
                store.close()


if __name__ == "__main__":
    main()
