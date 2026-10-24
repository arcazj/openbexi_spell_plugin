"""Actual HTTP peers cannot redirect or proxy the Context-owned DSS reader."""

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "driver_plugin/src")]
from openbexi_spell_dss.fenced_transport import Transport  # noqa: E402
from dss.local import create_servers  # noqa: E402
from dss.server import ApiHandler  # noqa: E402


@contextmanager
def endpoint(*, redirect=None, marker="fixed", status=200):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(302 if redirect else status)
            raw = b"" if redirect else json.dumps(dict(marker=marker)).encode()
            if redirect:
                self.send_header("Location", redirect)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            yield "http://127.0.0.1:" + str(server.server_port), requests
        finally:
            server.shutdown()
            thread.join(timeout=3)
            assert not thread.is_alive()


def reader(url):
    value = Transport.__new__(Transport)
    value.url = url
    value.metadata_admission = threading.BoundedSemaphore(3)
    return value


def test_redirect_is_rejected_before_contacting_another_actual_http_authority():
    with endpoint(marker="unapproved") as (target, target_requests):
        with endpoint(redirect=target + "/private-state") as (front, front_requests):
            with pytest.raises(ValueError, match="redirects are not permitted"):
                reader(front).get("state")
        assert front_requests == ["/api/v1/state"]
        assert target_requests == []


def test_environment_proxy_and_unlisted_path_cannot_replace_the_fixed_peer(monkeypatch):
    with endpoint(marker="proxy") as (proxy, proxy_requests):
        with endpoint() as (fixed, fixed_requests):
            for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
                monkeypatch.setenv(name, proxy)
            for name in ("no_proxy", "NO_PROXY"):
                monkeypatch.setenv(name, "")
            assert reader(fixed).get("telemetry") == dict(marker="fixed")
            with pytest.raises(ValueError, match="path is not permitted"):
                reader(fixed).get("../private-state")
        assert fixed_requests == ["/api/v1/telemetry"]
        assert proxy_requests == []


def test_fixed_endpoint_http_error_closes_its_response_without_success():
    with endpoint(status=503) as (fixed, requests):
        with pytest.raises(HTTPError) as denied:
            reader(fixed).get("state")
        assert denied.value.code == 503 and denied.value.fp.closed
        assert requests == ["/api/v1/state"]


def test_inherited_telemetry_samples_share_state_admission_at_actual_http_boundary(
    tmp_path, monkeypatch
):
    runtime, tcp, api = create_servers(tmp_path / "telemetry.sqlite", 0)
    release, three, fourth = (threading.Event() for _ in range(3))
    lock = threading.Lock()
    entered = []
    original = ApiHandler.do_GET

    def held(handler):
        if handler.path == "/api/v1/telemetry":
            with lock:
                entered.append(handler.path)
                if len(entered) >= 3:
                    three.set()
                if len(entered) >= 4:
                    fourth.set()
            if not release.wait(1):
                raise TimeoutError("Test metadata release not signalled")
        return original(handler)

    monkeypatch.setattr(ApiHandler, "do_GET", held)
    thread = threading.Thread(target=api.serve_forever)
    thread.start()
    transport = None
    try:
        transport = Transport(f"http://127.0.0.1:{api.server_port}", tcp.server_address)
        item = transport.database.telemetry[0]["item_id"]
        start = threading.Barrier(11)

        def sample(_):
            start.wait(timeout=2)
            return transport.sample(item)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(sample, index) for index in range(10)]
            try:
                start.wait(timeout=2)
                assert three.wait(1), "Expected three admitted metadata readers"
                assert not fourth.wait(0.075), "Telemetry bypassed the three-reader bound"
            finally:
                release.set()
            answers = [future.result(timeout=2) for future in futures]
        assert len(answers) == 10 and all(row["item_id"] == item for row in answers)
        assert len(entered) == 10  # No implicit transport retry.
        assert runtime.engine.state()["core"]["commands_executed"] == 0
    finally:
        release.set()
        if transport is not None:
            transport.close()
        api.shutdown()
        api.server_close()
        thread.join(timeout=3)
        tcp.server_close()
        runtime.engine.close()
        assert not thread.is_alive()


def test_full_metadata_budget_denies_before_any_http_request():
    with endpoint() as (fixed, requests):
        transport = reader(fixed)
        for _ in range(3):
            assert transport.metadata_admission.acquire(blocking=False)
        with pytest.raises(TimeoutError, match="metadata admission busy"):
            transport.get("telemetry")
        assert requests == []
