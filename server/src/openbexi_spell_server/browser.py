"""Opt-in same-origin browser workspace and certificate-scoped monitoring WebSocket."""

import importlib
from importlib.resources import files
import re
import threading
import time
from urllib.parse import urlsplit

from .contracts import Fault, canonical, decode, exact
from .gateway import Gateway


class BrowserWorkspace:
    def __init__(self, gateway, origin, hosts, max_handlers):
        target = urlsplit(origin) if isinstance(origin, str) else None
        if (
            not isinstance(gateway, Gateway)
            or target is None
            or target.scheme != "https"
            or origin != "https://" + target.netloc
            or not target.hostname
            or target.username
            or target.password
            or target.netloc not in hosts
            or max_handlers < 8
        ):
            raise ValueError(
                "Browser workspace requires an exact HTTPS Gateway origin and at least eight handler slots"
            )
        # Load the declared optional dependencies at startup, before admitting browsers.
        self.wsproto = importlib.import_module("wsproto")
        self.events = importlib.import_module("wsproto.events")
        self.protocol_error = importlib.import_module("wsproto.utilities").ProtocolError
        self.origin, self.host, self.gateway = origin, target.netloc, gateway
        self.streams = threading.BoundedSemaphore(min(32, max_handlers - 6))

    def validate_request(self, handler):
        origin = handler.headers.get_all("Origin", [])
        requires_origin = handler.command == "POST" or bool(handler.headers.get_all("Upgrade"))
        allowed = ([self.origin],) if requires_origin else ([], [self.origin])
        if handler.headers.get_all("Host") != [self.host] or origin not in allowed:
            raise Fault(403, "browser_origin_denied")
        if handler.headers.get_all("Sec-Fetch-Site", []) not in ([], ["same-origin"], ["none"]):
            raise Fault(403, "browser_origin_denied")

    def handle(self, handler, identity, body):
        assets = {
            "/workspace/": ("index.html", "text/html; charset=utf-8"),
            "/workspace/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/workspace/app.css": ("app.css", "text/css; charset=utf-8"),
        }
        if handler.command == "GET" and handler.path in assets:
            name, media = assets[handler.path]
            raw = files("openbexi_spell_server").joinpath("browser_assets", name).read_bytes()
            handler.send_response(200)
            handler.send_header("Content-Type", media)
            handler.send_header("Content-Length", str(len(raw)))
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("Referrer-Policy", "no-referrer")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.send_header("X-Frame-Options", "DENY")
            handler.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self' wss://"
                + self.host
                + "; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            )
            handler.end_headers()
            handler.wfile.write(raw)
            return
        stream = re.fullmatch(
            r"/workspace/contexts/([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})/events", handler.path
        )
        if handler.command == "GET" and stream:
            self.websocket(handler, identity, stream.group(1))
            return
        if not handler.path.startswith("/workspace/v1/") or handler.headers.get_all("Upgrade"):
            raise Fault(404, "route_not_available")
        # The fixed Listener rechecks configured subject scope, permission and
        # controller proof. Browser headers never leave the Gateway.
        response = self.gateway.handle(
            handler.command,
            handler.path.removeprefix("/workspace"),
            handler.headers,
            body,
            identity=identity,
        )
        handler.reply(200, response)

    def websocket(self, handler, identity, context):
        if not self.streams.acquire(blocking=False):
            raise Fault(503, "browser_monitor_capacity_reached")
        try:
            self._monitor(handler, identity, "/v1/contexts/" + context + "/events")
        finally:
            self.streams.release()

    def _monitor(self, handler, identity, path):
        ws = self.wsproto.WSConnection(self.wsproto.ConnectionType.SERVER)
        try:
            headers = [(k.encode("ascii"), v.encode("latin1")) for k, v in handler.headers.items()]
            ws.initiate_upgrade_connection(headers, handler.path)
            request = next(ws.events())
            if not isinstance(request, self.events.Request) or request.subprotocols != [
                "openbexi.events.v1"
            ]:
                raise Fault(400, "browser_monitor_protocol_required")
        except (self.protocol_error, StopIteration, UnicodeError) as error:
            raise Fault(400, "invalid_browser_upgrade") from error
        # Authorize execution:read before responding HTTP 101. Each later
        # replay rechecks the current listener scope and Context read policy.
        self.gateway.handle(
            "POST", path, handler.headers, {"after_sequence": 0, "limit": 1}, identity=identity
        )
        handler.connection.sendall(
            ws.send(self.events.AcceptConnection(subprotocol="openbexi.events.v1"))
        )
        handler.watchdog.cancel()
        handler.close_connection = True
        handler.connection.settimeout(4)
        end = time.monotonic() + 60
        received = bytearray()
        last_page = 0.0
        try:
            while time.monotonic() < end:
                data = handler.rfile.read1(1024)
                if not data:
                    return
                ws.receive_data(data)
                for event in ws.events():
                    if isinstance(event, self.events.CloseConnection):
                        handler.connection.sendall(ws.send(event.response()))
                        return
                    if isinstance(event, self.events.Ping):
                        handler.connection.sendall(ws.send(event.response()))
                        continue
                    if not isinstance(event, self.events.TextMessage):
                        raise ValueError("Only a bounded replay cursor is supported")
                    received.extend(event.data.encode("utf-8"))
                    if len(received) > 256:
                        raise ValueError("Replay cursor exceeds its bound")
                    if not event.message_finished:
                        continue
                    cursor = exact(decode(bytes(received)), {"after_sequence"})
                    received.clear()
                    if (
                        type(cursor["after_sequence"]) is not int
                        or not 0 <= cursor["after_sequence"] < 2**63
                        or time.monotonic() - last_page < 0.15
                    ):
                        raise ValueError("Invalid replay cursor or read cadence")
                    last_page = time.monotonic()
                    page = self.gateway.handle(
                        "POST", path, handler.headers, dict(cursor, limit=32), identity=identity
                    )
                    handler.connection.sendall(
                        ws.send(self.events.TextMessage(data=canonical(page["result"]).decode()))
                    )
            handler.connection.sendall(ws.send(self.events.CloseConnection(code=1000)))
        except (self.protocol_error, ValueError, Fault):
            try:
                handler.connection.sendall(ws.send(self.events.CloseConnection(code=1008)))
            except (self.protocol_error, OSError):
                pass
        except OSError:
            return
