"""Certificate-authenticated desktop edge; fixed Listener origin, never a proxy."""

import hashlib
import http.client
import socket
import threading
from urllib.parse import urlsplit

from .contracts import MAX_BODY, Fault, canonical, decode, fingerprint, identifier
from .services import one_header


class Gateway:
    def __init__(self, listener_url, listener_fingerprint, tls, clients):
        target = urlsplit(listener_url)
        if (
            target.scheme != "https"
            or not target.hostname
            or target.username
            or target.password
            or target.path not in ("", "/")
            or target.query
            or target.fragment
        ):
            raise ValueError("Listener must be a configured HTTPS origin")
        self.host, self.port = target.hostname, target.port or 443
        self.listener_fingerprint, self.tls = fingerprint(listener_fingerprint), tls
        if type(clients) is not list or not 1 <= len(clients) <= 128:
            raise ValueError("Configure one to 128 desktop certificate pins")
        self.clients = frozenset(fingerprint(peer) for peer in clients)

    def authenticate(self, peer, headers):
        if headers.get_all("X-OpenBEXI-Client-Fingerprint"):
            raise Fault(403, "unexpected_client_identity")
        if peer not in self.clients:
            raise Fault(403, "user_identity_denied")
        return peer

    def handle(self, method, path, headers, body, *, identity=None):
        if identity not in self.clients:
            raise Fault(403, "user_identity_denied")
        values = {"X-OpenBEXI-Client-Fingerprint": identity}
        if method == "GET" and path in ("/v1/health", "/v1/contexts"):
            pass
        else:
            parts = path.split("/")
            if len(parts) != 5 or parts[1:3] != ["v1", "contexts"]:
                raise Fault(404, "route_not_available")
            identifier(parts[3])
            if method == "GET" and parts[4] in (
                "health",
                "snapshot",
                "blackboard",
                "procedures",
                "executions",
            ):
                pass
            elif method == "POST" and parts[4] in ("authority", "blackboard", "commands"):
                values["Idempotency-Key"] = identifier(one_header(headers, "Idempotency-Key"))
            elif method == "POST" and parts[4] == "events":
                # Read-only replay: no mutation/idempotency key is transmitted.
                if headers.get_all("Idempotency-Key"):
                    raise Fault(400, "unexpected_idempotency_key")
            else:
                raise Fault(404, "route_not_available")
        raw = None if method == "GET" else canonical(body)
        if raw is not None:
            values["Content-Type"] = "application/json"
        connection = http.client.HTTPSConnection(self.host, self.port, context=self.tls, timeout=2)
        watchdog = None
        try:
            connection.connect()
            wire = connection.sock

            def expire():
                try:
                    wire.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            watchdog = threading.Timer(4, expire)
            watchdog.daemon = True
            watchdog.start()
            certificate = wire.getpeercert(binary_form=True)
            if not certificate:
                raise Fault(503, "listener_identity_unavailable")
            peer = hashlib.sha256(certificate).hexdigest()
            if peer != self.listener_fingerprint:
                raise Fault(503, "listener_identity_unavailable")
            connection.request(method, path, raw, values)
            response = connection.getresponse()
            result = decode(response.read(MAX_BODY + 1))
            if response.status != 200:
                status = (
                    response.status if response.status in (400, 403, 404, 409, 413, 503) else 503
                )
                raise Fault(status, "listener_request_denied")
            if type(result) is not dict or result.get("schema") != "openbexi.listener/1":
                raise Fault(503, "listener_protocol_error")
            return result
        except (OSError, http.client.HTTPException) as error:
            raise Fault(503, "listener_unavailable") from error
        finally:
            if watchdog:
                watchdog.cancel()
            connection.close()
