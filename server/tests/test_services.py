import http.client
import json
import socket
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from openbexi_spell_server.contracts import Actor, Fault, canonical, envelope
from openbexi_spell_server.services import Context, Listener
from openbexi_spell_server.store import ContextStore
from openbexi_spell_server.transport import Route, Server

ALICE, BOB, CAROL = "a" * 64, "b" * 64, "c" * 64
ALL = ["context:read", "blackboard:read", "blackboard:admin"]


@contextmanager
def serving(app, tls):
    server = Server(("127.0.0.1", 0), app, tls)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def request(server, tls, path, *, subject=ALICE, payload=None, method=None, headers=None):
    connection = http.client.HTTPSConnection(
        "localhost", server.server_port, context=tls, timeout=3
    )
    values = {} if subject is None else {"X-OpenBEXI-Client-Fingerprint": subject}
    values.update(headers or {})
    body = None
    if payload is not None:
        body = payload if isinstance(payload, bytes) else canonical(payload)
        values["Content-Type"] = "application/json"
    try:
        connection.request(method or ("POST" if body is not None else "GET"), path, body, values)
        answer = connection.getresponse()
        return answer.status, json.loads(answer.read())
    finally:
        connection.close()


@pytest.fixture
def cluster(tmp_path, pki):
    a, b = ContextStore(tmp_path / "A", "A"), ContextStore(tmp_path / "B", "B")
    apps = {
        "A": Context(a, pki["listener"]["pin"], {"alice": ALL, "bob": ALL[:2]}),
        "B": Context(b, pki["listener"]["pin"], {"alice": ALL, "carol": ALL[:2]}),
    }
    try:
        with serving(apps["A"], pki["context-a"]["server"]) as sa:
            with serving(apps["B"], pki["context-b"]["server"]) as sb:
                routes = {
                    "A": Route(
                        f"https://localhost:{sa.server_port}",
                        pki["context-a"]["pin"],
                        pki["listener"]["client"],
                    ),
                    "B": Route(
                        f"https://localhost:{sb.server_port}",
                        pki["context-b"]["pin"],
                        pki["listener"]["client"],
                    ),
                }
                listener = Listener(
                    pki["edge"]["pin"],
                    {ALICE: "alice", BOB: "bob", CAROL: "carol"},
                    {"alice": ["A", "B"], "bob": ["A"], "carol": ["B"]},
                    routes,
                )
                with serving(listener, pki["listener"]["server"]) as sl:
                    yield dict(
                        listener=sl, A=sa, B=sb, stores={"A": a, "B": b}, apps=apps, routes=routes
                    )
    finally:
        a.close()
        b.close()


def test_real_tls_discovery_is_scoped_and_roles_are_not_certificate_ca_membership(cluster, pki):
    server = cluster["listener"]
    status, body = request(server, pki["edge"]["client"], "/v1/contexts", subject=BOB)
    assert status == 200 and body["contexts"] == ["A"]
    for peer in ("worker", "context-a", "listener"):
        assert request(server, pki[peer]["client"], "/v1/contexts")[0] == 403
    assert request(server, pki["edge"]["client"], "/v1/contexts", subject="d" * 64)[0] == 403
    assert request(server, pki["edge"]["client"], "/v1/contexts/B/snapshot", subject=BOB)[0] == 403


def test_context_requires_listener_identity_and_its_own_local_acl(cluster, pki):
    server = cluster["A"]
    body = envelope("A", "alice", "health", {})
    for peer in ("edge", "worker", "context-a"):
        assert request(server, pki[peer]["client"], "/v1/rpc", subject=None, payload=body)[0] == 403
    body = envelope("A", "carol", "health", {})
    assert (
        request(server, pki["listener"]["client"], "/v1/rpc", subject=None, payload=body)[0] == 403
    )


def test_permission_checks_precede_idempotency_replay_after_revocation(cluster, pki):
    server = cluster["listener"]
    path = "/v1/contexts/A/blackboard"
    body = dict(key="shared", expected_revision=0, value=123)
    headers = {"Idempotency-Key": "request-1"}
    first = request(server, pki["edge"]["client"], path, payload=body, headers=headers)
    assert first[0] == 200
    assert request(server, pki["edge"]["client"], path, payload=body, headers=headers) == first
    assert (
        request(server, pki["edge"]["client"], path, subject=BOB, payload=body, headers=headers)[0]
        == 403
    )
    cluster["apps"]["A"].subjects["alice"] = Actor("alice", frozenset(ALL[:2]))
    assert request(server, pki["edge"]["client"], path, payload=body, headers=headers)[0] == 403
    assert cluster["stores"]["A"].snapshot()["blackboard"]["shared"]["revision"] == 1


def test_snapshot_does_not_leak_values_and_context_data_is_separate(cluster, pki):
    cluster["stores"]["A"].cas(
        "alice", "one", dict(key="shared", expected_revision=0, value="A-data")
    )
    server = cluster["listener"]
    status, body = request(server, pki["edge"]["client"], "/v1/contexts/A/snapshot", subject=BOB)
    assert status == 200 and "A-data" not in json.dumps(body)
    status, body = request(
        server, pki["edge"]["client"], "/v1/contexts/B/blackboard", subject=CAROL
    )
    assert status == 200 and body["result"]["blackboard"] == {}


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Host": "attacker.invalid"}, 400),
        ({"Origin": "https://attacker.invalid"}, 403),
        ({"Cookie": "session=forged"}, 403),
        ({"Authorization": "Bearer forged"}, 403),
        ({"X-Forwarded-User": "alice"}, 403),
        ({"X-OpenBEXI-User": "alice"}, 403),
    ],
)
def test_host_origin_session_and_forwarded_identity_denial(cluster, pki, headers, status):
    assert (
        request(cluster["listener"], pki["edge"]["client"], "/v1/contexts", headers=headers)[0]
        == status
    )


@pytest.mark.parametrize(
    "path",
    [
        "/v1/contexts/A/executions",
        "/v1/worker/start",
        "/v1/dap",
        "/v1/contexts/A/snapshot?token=forged",
        "/v1/contexts/%41/snapshot",
    ],
)
def test_execution_and_alternate_control_routes_are_absent(cluster, pki, path):
    assert request(cluster["listener"], pki["edge"]["client"], path)[0] in (400, 404)


def test_malformed_json_framing_and_duplicate_identity_headers(cluster, pki):
    server = cluster["listener"]
    path = "/v1/contexts/A/blackboard"
    assert request(server, pki["edge"]["client"], path, payload=b'{"x":1,"x":2}')[0] == 400
    connection = http.client.HTTPSConnection(
        "localhost", server.server_port, context=pki["edge"]["client"]
    )
    try:
        connection.putrequest("GET", "/v1/contexts")
        connection.putheader("X-OpenBEXI-Client-Fingerprint", ALICE)
        connection.putheader("X-OpenBEXI-Client-Fingerprint", BOB)
        connection.endheaders()
        assert connection.getresponse().status == 403
    finally:
        connection.close()
    assert (
        request(
            server,
            pki["edge"]["client"],
            path,
            payload={},
            headers={"Transfer-Encoding": "chunked", "Content-Length": "2"},
        )[0]
        == 400
    )


def test_wrong_context_pin_prevents_transmitting_any_delegation(cluster, pki):
    target = cluster["A"]
    route = Route(
        f"https://localhost:{target.server_port}",
        pki["context-b"]["pin"],
        pki["listener"]["client"],
    )
    before = cluster["stores"]["A"].snapshot()
    with pytest.raises(Fault, match="context_identity_unavailable"):
        route.call(
            envelope(
                "A",
                "alice",
                "blackboard.cas",
                dict(key="hidden", expected_revision=0, value=1),
                "one",
            )
        )
    assert cluster["stores"]["A"].snapshot() == before


def test_unavailable_context_does_not_block_other_context(cluster, pki):
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    cluster["routes"]["A"] = Route(
        f"https://localhost:{port}", pki["context-a"]["pin"], pki["listener"]["client"]
    )
    # Listener has its own mapping; replace only the explicitly configured route.
    cluster["listener"].application.contexts["A"] = cluster["routes"]["A"]
    assert request(cluster["listener"], pki["edge"]["client"], "/v1/contexts/A/health")[0] == 503
    assert request(cluster["listener"], pki["edge"]["client"], "/v1/contexts/B/health")[0] == 200


def test_concurrent_tls_clients_have_consistent_context_revision(cluster, pki):
    def write(n):
        return request(
            cluster["listener"],
            pki["edge"]["client"],
            "/v1/contexts/A/blackboard",
            payload=dict(key="race", expected_revision=0, value=n),
            headers={"Idempotency-Key": "race-" + str(n)},
        )[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(20)))
    assert results.count(200) == 1
    assert results.count(409) == 19


def test_missing_client_certificate_fails_tls(cluster, pki):
    tls = ssl.create_default_context(cafile=str(pki["ca"]))
    with pytest.raises((OSError, http.client.HTTPException)):
        request(cluster["listener"], tls, "/v1/health")


def test_slow_handshake_does_not_block_the_accept_loop(cluster, pki):
    raw = socket.create_connection(("127.0.0.1", cluster["listener"].server_port), timeout=2)
    try:
        assert request(cluster["listener"], pki["edge"]["client"], "/v1/health")[0] == 200
    finally:
        raw.close()
