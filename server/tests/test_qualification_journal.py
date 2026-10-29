"""A real interrupted pytest run must retain the preceding failure evidence."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time


def test_completed_failure_survives_killed_pytest_session(tmp_path):
    tests = tmp_path / "test_interrupted.py"
    tests.write_text(
        "import sys, time\n"
        "from pathlib import Path\n"
        "def test_00_failure():\n"
        "    print('retained stdout before interruption')\n"
        "    print('retained stderr before interruption', file=sys.stderr)\n"
        "    assert 123 == 456, 'retained assertion before interruption'\n"
        "def test_01_incomplete():\n"
        "    Path('blocked-in-call').write_text('started')\n"
        "    time.sleep(30)\n"
    )
    evidence = tmp_path / "evidence"
    with (
        (tmp_path / "pytest.stdout").open("wb") as stdout,
        (tmp_path / "pytest.stderr").open("wb") as stderr,
    ):
        child = subprocess.Popen(
            [sys.executable, "-m", "pytest", "-p", "qualification_journal", str(tests), "-q"],
            cwd=tmp_path,
            env=dict(
                os.environ,
                PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                PYTHONPATH=str(Path(__file__).resolve().parent),
                OPENBEXI_SERVER_EVIDENCE_DIR=str(evidence),
            ),
            stdout=stdout,
            stderr=stderr,
        )
        deadline = time.monotonic() + 10
        rows = []
        try:
            while child.poll() is None and time.monotonic() < deadline:
                journals = list(evidence.glob("tests.results-*.jsonl"))
                if journals:
                    raw = journals[0].read_bytes()
                    # A reader does not discard or interpret an unfinished last line.
                    lines = raw.splitlines(keepends=True)
                    rows = [json.loads(line) for line in lines if line.endswith(b"\n")]
                    if (tmp_path / "blocked-in-call").exists() and any(
                        row["kind"] == "test_start"
                        and row["nodeid"].endswith("::test_01_incomplete")
                        for row in rows
                    ):
                        break
                time.sleep(0.01)
            assert (tmp_path / "blocked-in-call").exists() and any(
                row["kind"] == "test_start" and row["nodeid"].endswith("::test_01_incomplete")
                for row in rows
            ), (tmp_path / "pytest.stderr").read_text()
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
    assert child.returncode != 0
    journals = list(evidence.glob("tests.results-*.jsonl"))
    assert len(journals) == 1
    rows = [json.loads(line) for line in journals[0].read_text().splitlines()]
    assert [row["sequence"] for row in rows] == list(range(1, len(rows) + 1))
    assert {row["pid"] for row in rows} == {child.pid}
    failed = [row for row in rows if row["kind"] == "test_report" and row["outcome"] == "failed"]
    assert len(failed) == 1 and failed[0]["phase"] == "call"
    assert "retained assertion before interruption" in failed[0]["longrepr"]
    assert "123 == 456" in failed[0]["longrepr"]
    assert failed[0]["duration_seconds"] >= 0
    sections = dict(failed[0]["captured_sections"])
    assert "retained stdout before interruption" in sections["Captured stdout call"]
    assert "retained stderr before interruption" in sections["Captured stderr call"]
    assert not any(row["kind"] == "session_finish" for row in rows)
    assert not any(
        row["kind"] == "test_report"
        and row["nodeid"].endswith("::test_01_incomplete")
        and row["phase"] == "call"
        for row in rows
    )
