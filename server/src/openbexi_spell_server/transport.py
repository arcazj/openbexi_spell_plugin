"""Small internal mTLS transport; not a browser/WSS or general reverse proxy."""

import hashlib
import http.client
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit

from .contracts import MAX_BODY, Fault, canonical, decode, fingerprint


def tls_context(ca, certificate, key, *, server=False):
    purpose = ssl.Purpose.CLIENT_AUTH if server else ssl.Purpose.SERVER_AUTH
    result = ssl.create_default_context(purpose, cafile=str(ca))
    result.minimum_version = ssl.TLSVersion.TLSv1_3
    result.verify_mode = ssl.CERT_REQUIRED
    result.load_cert_chain(str(certificate), str(key))
    return result


class Route:
    """Immutable configured destination. Pin verification precedes delegation transmission."""

    def __init__(self, url, peer_fingerprint, tls):
        target = urlsplit(url)
        if (
            target.scheme != "https"
            or not target.hostname
            or target.username
            or target.password
            or target.path not in ("", "/")
            or target.query
            or target.fragment
        ):
            raise ValueError("Context endpoint must be a configured HTTPS origin")
        self.host, self.port = target.hostname, target.port or 443
        self.peer_fingerprint, self.tls = fingerprint(peer_fingerprint), tls

    def call(self, request, *, path="/v1/rpc", schema="openbexi.context/1"):
        if (path, schema) not in (
            ("/v1/rpc", "openbexi.context/1"),
            ("/v1/worker/challenge", "openbexi.worker/1"),
            ("/v1/worker/verify", "openbexi.worker/1"),
            ("/v1/worker/consume", "openbexi.worker/2"),
            ("/v1/worker/check", "openbexi.worker/2"),
            ("/v1/worker/event", "openbexi.worker/2"),
            ("/v1/worker/driver", "openbexi.worker/2"),
            ("/v1/worker/pause-poll", "openbexi.worker/2"),
            ("/v1/worker/pause-report", "openbexi.worker/2"),
            ("/v1/worker/child-admit", "openbexi.worker/2"),
            ("/v1/worker/child-consume", "openbexi.worker/2"),
            ("/v1/worker/control-admit", "openbexi.worker/2"),
            ("/v1/worker/control-report", "openbexi.worker/2"),
            ("/v1/worker/control-forward", "openbexi.worker/2"),
        ):
            raise ValueError("Unconfigured RPC route")
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

            watchdog = threading.Timer(5, expire)
            watchdog.daemon = True
            watchdog.start()
            certificate = connection.sock.getpeercert(binary_form=True)
            if not certificate:
                raise Fault(503, "context_identity_unavailable")
            peer = hashlib.sha256(certificate).hexdigest()
            if peer != self.peer_fingerprint:
                raise Fault(503, "context_identity_unavailable")
            connection.request(
                "POST", path, canonical(request), {"Content-Type": "application/json"}
            )
            response = connection.getresponse()
            raw = response.read(MAX_BODY + 1)
            body = decode(raw)
            if response.status != 200:
                # Do not forward arbitrary upstream body text or configuration details.
                if response.status in (400, 403, 404, 409, 413, 503):
                    raise Fault(response.status, "context_request_denied")
                raise Fault(503, "context_unavailable")
            if type(body) is not dict or set(body) != {"schema", "result"}:
                raise Fault(503, "context_protocol_error")
            if body["schema"] != schema:
                raise Fault(503, "context_protocol_error")
            return body["result"]
        except (OSError, http.client.HTTPException) as error:
            raise Fault(503, "context_unavailable") from error
        finally:
            if watchdog:
                watchdog.cancel()
            connection.close()


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 64

    def __init__(self, address, application, tls, *, allowed_hosts=None, max_handlers=16):
        if type(max_handlers) is not int or not 1 <= max_handlers <= 64:
            raise ValueError("Invalid handler bound")
        self.application, self.tls = application, tls
        self.admission = threading.BoundedSemaphore(max_handlers)
        super().__init__(address, Handler)
        port = self.server_port
        self.allowed_hosts = set(allowed_hosts or [f"{address[0]}:{port}"])
        if address[0] in ("127.0.0.1", "localhost") and not allowed_hosts:
            self.allowed_hosts.add(f"localhost:{port}")

    def process_request(self, request, client_address):
        if not self.admission.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.admission.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.admission.release()

    def handle_error(self, request, client_address):
        # Expected failed TLS handshakes/disconnects must not log request data.
        pass


class Handler(BaseHTTPRequestHandler):
    server: Server
    protocol_version = "HTTP/1.0"
    server_version = "OpenBEXI-internal"
    sys_version = ""

    def setup(self):
        # Handshake is in the bounded handler thread, never the accept loop.
        self.request.settimeout(2)
        self.watchdog = threading.Timer(5, self.expire)
        self.watchdog.daemon = True
        self.watchdog.start()
        try:
            self.request = self.server.tls.wrap_socket(self.request, server_side=True)
            super().setup()
        except BaseException:
            self.watchdog.cancel()
            self.request.close()
            raise

    def expire(self):
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def finish(self):
        try:
            super().finish()
        finally:
            self.watchdog.cancel()
            # wrap_socket detached the accepted raw socket. The server's
            # shutdown_request(raw_socket) cannot close this TLS owner.
            self.request.close()

    def log_message(self, *_):
        pass

    def reply(self, status, body):
        raw = canonical(body)
        if len(raw) > MAX_BODY:
            status, raw = 503, canonical({"error": "response_capacity_reached"})
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def route(self):
        self.body_consumed = False
        try:
            if self.command not in ("GET", "POST"):
                raise Fault(405, "method_not_available")
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or hosts[0] not in self.server.allowed_hosts:
                raise Fault(400, "host_denied")
            if sum(len(k) + len(v) for k, v in self.headers.items()) > 8192:
                raise Fault(413, "headers_too_large")
            if any(self.headers.get_all(k) for k in ("Origin", "Cookie", "Authorization")):
                raise Fault(403, "browser_session_not_available")
            if any(k.lower().startswith("x-forwarded-") for k in self.headers):
                raise Fault(403, "forwarded_identity_denied")
            if any(
                k.lower().startswith("x-openbexi-") and k.lower() != "x-openbexi-client-fingerprint"
                for k in self.headers
            ):
                raise Fault(403, "unknown_identity_header")
            if "?" in self.path or "#" in self.path or "%" in self.path:
                raise Fault(400, "noncanonical_path")
            peer = hashlib.sha256(self.connection.getpeercert(binary_form=True)).hexdigest()
            identity = self.server.application.authenticate(peer, self.headers)
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get_all("Transfer-Encoding") or len(lengths) > 1:
                raise Fault(400, "invalid_framing")
            if self.command == "GET":
                if lengths and lengths != ["0"]:
                    raise Fault(400, "unexpected_body")
                body = None
            else:
                if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                    raise Fault(400, "content_length_required")
                if len(lengths[0]) > 6 or not 2 <= int(lengths[0]) <= MAX_BODY:
                    raise Fault(413, "body_too_large")
                if self.headers.get_all("Content-Type") != ["application/json"]:
                    raise Fault(415, "json_required")
                self.body_consumed = True
                raw = self.rfile.read(int(lengths[0]))
                if len(raw) != int(lengths[0]):
                    raise Fault(400, "truncated_body")
                body = decode(raw)
            result = self.server.application.handle(
                self.command, self.path, self.headers, body, identity=identity
            )
            self.reply(200, result)
        except Fault as error:
            # Consume only an explicitly bounded rejected body. Closing TLS
            # over unread TCP data can otherwise reset a valid denial response.
            lengths = self.headers.get_all("Content-Length", [])
            if (
                not self.body_consumed
                and len(lengths) == 1
                and lengths[0].isascii()
                and lengths[0].isdigit()
                and len(lengths[0]) <= 6
                and int(lengths[0]) <= MAX_BODY
            ):
                try:
                    self.rfile.read(int(lengths[0]))
                except OSError:
                    pass
            self.reply(error.status, {"error": error.code})
        except (TimeoutError, ConnectionError, OSError):
            self.close_connection = True
        except Exception:
            self.reply(500, {"error": "internal_error"})

    do_GET = route
    do_POST = route
    do_PUT = route
    do_DELETE = route
    do_PATCH = route
