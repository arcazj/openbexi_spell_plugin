"""The browser profile uses its own origin, mTLS identity and read-only WSS channel."""

from http.client import HTTPSConnection
import json
import socket

import pytest
from wsproto import ConnectionType, WSConnection
from wsproto.events import AcceptConnection, CloseConnection, Request, TextMessage

from openbexi_spell_server.browser import BrowserWorkspace

pytest_plugins = ("test_ide_integration",)


def http(server, tls, path, *, headers=None, payload=None):
    conn = HTTPSConnection("localhost", server.server_port, context=tls, timeout=3)
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        conn.request(
            "POST" if body else "GET",
            path,
            body,
            {**({"Content-Type": "application/json"} if body else {}), **(headers or {})},
        )
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def enable(cluster):
    server = cluster["gateway"]
    origin = f"https://localhost:{server.server_port}"
    server.browser = BrowserWorkspace(cluster["app"], origin, server.allowed_hosts, 32)
    return server, origin


def test_browser_routes_are_explicitly_enabled_and_same_origin(desktop_cluster, pki):
    server = desktop_cluster["gateway"]
    tls = pki["alice"]["client"]
    assert http(server, tls, "/workspace/")[0] == 404
    server, origin = enable(desktop_cluster)
    code, headers, html = http(server, tls, "/workspace/")
    assert code == 200 and b"Execution workspace" in html
    assert (
        headers["X-Frame-Options"] == "DENY"
        and "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    )
    assert http(server, tls, "/workspace/v1/contexts", headers={"Origin": origin})[0] == 200
    assert http(server, tls, "/v1/contexts", headers={"Origin": origin})[0] == 403
    assert http(server, pki["worker"]["client"], "/workspace/")[0] == 403
    resource = "/workspace/v1/contexts/A/authority"
    key = {"Idempotency-Key": "test-browser-session"}
    payload = dict(method="session.open", payload={})
    for headers in (
        key,
        dict(key, Origin="https://other.example"),
        dict(key, Origin=origin, Cookie="test=1"),
    ):
        assert http(server, tls, resource, headers=headers, payload=payload)[0] == 403
    assert (
        http(
            server,
            pki["observer"]["client"],
            resource,
            headers=dict(key, Origin=origin),
            payload=payload,
        )[0]
        == 403
    )
    assert http(server, tls, resource, headers=dict(key, Origin=origin), payload=payload)[0] == 200


def test_websocket_replays_only_authorized_events_and_rejects_mutations(desktop_cluster, pki):
    server, origin = enable(desktop_cluster)
    tls = pki["observer"]["client"]
    host = f"localhost:{server.server_port}"
    before = desktop_cluster["store"].db.execute("SELECT count(*) FROM events").fetchone()[0]
    with (
        socket.create_connection(("localhost", server.server_port), timeout=3) as raw,
        tls.wrap_socket(raw, server_hostname="localhost") as wire,
    ):
        ws = WSConnection(ConnectionType.CLIENT)

        def send(event):
            wire.sendall(ws.send(event))

        def receive():
            while True:
                data = wire.recv(4096)
                assert data
                ws.receive_data(data)
                events = list(ws.events())
                if events:
                    return events[0]

        send(
            Request(
                host=host,
                target="/workspace/contexts/A/events",
                subprotocols=["openbexi.events.v1"],
                extra_headers=[(b"Origin", origin.encode())],
            )
        )
        assert isinstance(receive(), AcceptConnection)
        send(TextMessage(data='{"after_sequence":0}'))
        page = receive()
        assert isinstance(page, TextMessage)
        result = json.loads(page.data)
        assert (
            result["context_id"] == "A"
            and result["events"] == []
            and result["runtime_enabled"] is False
        )
        send(TextMessage(data='{"method":"session.open"}'))
        closed = receive()
        assert isinstance(closed, CloseConnection) and closed.code == 1008
    assert (
        desktop_cluster["store"].db.execute("SELECT count(*) FROM events").fetchone()[0] == before
    )


@pytest.mark.parametrize(
    "origin", ["http://localhost", "https://other.example", "https://localhost/path"]
)
def test_browser_configuration_requires_an_exact_allowed_gateway_origin(desktop_cluster, origin):
    with pytest.raises(ValueError):
        BrowserWorkspace(desktop_cluster["app"], origin, {"localhost"}, 32)
