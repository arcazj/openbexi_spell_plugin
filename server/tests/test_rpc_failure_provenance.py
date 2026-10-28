"""Actual mTLS failures retain bounded local provenance without changing wire errors."""

from concurrent.futures import ThreadPoolExecutor
import argparse
import ast
import json
from pathlib import Path
import threading
import traceback

import pytest

from openbexi_spell_server import transport
from openbexi_spell_server.contracts import Fault, decode


class Application:
    def authenticate(self, *_):
        return "worker"

    def handle(self, _method, _path, _headers, body, **_):
        if body.get("deny"):
            raise Fault(body["status"], body["deny"])
        return {"schema": "openbexi.worker/2", "result": {"unchanged": True}}


@pytest.fixture
def endpoint(pki):
    server = transport.Server(("127.0.0.1", 0), Application(), pki["context-a"]["server"])
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    route = transport.Route(
        f"https://127.0.0.1:{server.server_port}", pki["context-a"]["pin"], pki["worker"]["client"]
    )
    try:
        yield route
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def deny(endpoint, code="execution_busy", status=503):
    with pytest.raises(Fault) as info:
        endpoint.call(
            {"deny": code, "status": status, "private": "request-secret-never-retain"},
            path="/v1/worker/control-report",
            schema="openbexi.worker/2",
        )
    return info.value


def test_real_control_report_denial_retains_status_and_original_code(endpoint):
    error = deny(endpoint)
    assert (type(error), error.status, error.code) == (Fault, 503, "context_request_denied")
    provenance = error.rpc_provenance
    assert provenance["path"] == "/v1/worker/control-report"
    assert provenance["http_status"] == 503
    assert provenance["upstream_code"] == "execution_busy"
    assert provenance["phase"] == "response_validation"
    assert provenance["started_ns"] < provenance["finished_ns"]
    assert 0 <= provenance["thread_cpu_ns"] <= provenance["finished_ns"] - provenance["started_ns"]
    assert "request-secret" not in json.dumps(provenance)
    assert endpoint.call({}, path="/v1/worker/control-report", schema="openbexi.worker/2") == {
        "unchanged": True
    }


def test_unlisted_response_code_is_redacted_and_original_denial_is_preserved(endpoint):
    error = deny(endpoint, "private-upstream-message-never-retain", 409)
    assert (error.status, error.code) == (409, "context_request_denied")
    assert error.rpc_provenance["upstream_code"] == "unlisted_fault_code"
    assert "private-upstream" not in json.dumps(error.rpc_provenance)


def test_concurrent_faults_own_their_provenance(endpoint):
    cases = [
        ("execution_busy", 503),
        ("native_control_origin_fenced", 403),
        ("native_control_report_conflict", 409),
    ] * 3
    with ThreadPoolExecutor(max_workers=3) as pool:
        faults = list(pool.map(lambda case: deny(endpoint, *case), cases))
    assert len({id(error.rpc_provenance) for error in faults}) == len(cases)
    assert [
        (error.rpc_provenance["upstream_code"], error.rpc_provenance["http_status"])
        for error in faults
    ] == cases
    assert all(error.code == "context_request_denied" for error in faults)


def test_upstream_500_status_is_retained_when_public_status_is_503(endpoint):
    error = deny(endpoint, "state_unavailable", 500)
    assert (error.status, error.code) == (503, "context_unavailable")
    assert error.rpc_provenance["http_status"] == 500
    assert error.rpc_provenance["upstream_code"] == "state_unavailable"


def test_invalid_response_keeps_received_status_without_retaining_body(endpoint, monkeypatch):
    def malformed(handler, _status, _body):
        body = b"private-upstream-body-not-json"
        handler.send_response(503)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    monkeypatch.setattr(transport.Handler, "reply", malformed)
    error = deny(endpoint)
    assert error.code == "invalid_json"
    assert error.rpc_provenance["http_status"] == 503
    assert error.rpc_provenance["upstream_code"] is None
    assert error.rpc_provenance["phase"] == "response_decode"
    assert "private-upstream" not in json.dumps(error.rpc_provenance)


def test_connect_error_retains_phase_and_original_exception_without_text(endpoint, monkeypatch):
    def fail(_connection):
        raise TimeoutError("private-connection-details")

    monkeypatch.setattr(transport.http.client.HTTPSConnection, "connect", fail)
    error = deny(endpoint)
    assert (error.status, error.code) == (503, "context_unavailable")
    assert type(error.__cause__) is TimeoutError
    assert error.rpc_provenance["phase"] == "connect"
    assert error.rpc_provenance["http_status"] is None
    assert "private-connection" not in json.dumps(error.rpc_provenance)


def test_worker_failure_keeps_original_fault_status_and_rpc_provenance(
    endpoint, monkeypatch, tmp_path
):
    error = deny(endpoint)
    source = Path(__file__).resolve().parents[2] / "host_runtime/python/v08_worker.py"
    function = next(
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    config = tmp_path / "config.json"
    config.write_text("{}")
    monkeypatch.setattr("sys.argv", ["worker", "--config", str(config)])
    reports = []

    def run(_configuration):
        raise error

    namespace = {
        "__doc__": "worker failure provenance regression",
        "argparse": argparse,
        "Path": Path,
        "Fault": Fault,
        "decode": decode,
        "protect_runtime": lambda: None,
        "run": run,
        "traceback": traceback,
        "emit": lambda event, **fields: reports.append(dict(event=event, **fields)),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    assert namespace["main"]() == 1
    (failure,) = reports
    assert failure["event"] == "native-worker-failed"
    assert failure["hold_retained"] and not failure["runtime_enabled"]
    assert failure["causes"][0]["status"] == 503
    assert failure["causes"][0]["rpc_provenance"] == error.rpc_provenance
    assert "request-secret" not in json.dumps(failure)
