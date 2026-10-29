"""Retain ordered pytest results when the unchanged suite deadline interrupts it.

This is diagnostic evidence, not a substitute for a completed JUnit report or
passing qualification. Each pytest process owns one append-only JSONL file.
Successful reports are written without a Python buffer; failures and session
completion are additionally synced. A killed writer may leave an incomplete
last line, which readers must preserve rather than treating as a completed test.
"""

import json
import os
from pathlib import Path
import sys
import time
import uuid


class QualificationJournal:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"tests.results-{os.getpid()}-{uuid.uuid4().hex}.jsonl"
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600)
        self.sequence = 0

    def record(self, kind, *, sync=False, **fields):
        self.sequence += 1
        raw = (
            json.dumps(
                dict(
                    schema="openbexi.pytest-result-journal/1",
                    sequence=self.sequence,
                    kind=kind,
                    pid=os.getpid(),
                    unix_ns=time.time_ns(),
                    monotonic_ns=time.monotonic_ns(),
                    **fields,
                ),
                ensure_ascii=True,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        offset = 0
        while offset < len(raw):
            written = os.write(self.fd, raw[offset:])
            if written <= 0:
                raise OSError("qualification journal write made no progress")
            offset += written
        if sync:
            os.fsync(self.fd)

    def pytest_sessionstart(self, session):
        self.record(
            "session_start",
            executable=sys.executable,
            arguments=list(session.config.invocation_params.args),
            cwd=str(Path.cwd()),
            incomplete_session_is_not_a_pass=True,
        )

    def pytest_runtest_logstart(self, nodeid, location):
        self.record("test_start", nodeid=nodeid, location=list(location))

    def pytest_runtest_logreport(self, report):
        details = {}
        if report.failed or report.skipped:
            details = dict(
                longrepr=report.longreprtext,
                captured_sections=[list(section) for section in report.sections],
            )
        self.record(
            "test_report",
            sync=report.failed,
            nodeid=report.nodeid,
            phase=report.when,
            outcome=report.outcome,
            duration_seconds=report.duration,
            report_started_at=report.start,
            report_stopped_at=report.stop,
            **details,
        )

    def pytest_sessionfinish(self, session, exitstatus):
        self.record(
            "session_finish",
            sync=True,
            exitstatus=int(exitstatus),
            tests_collected=session.testscollected,
            tests_failed=session.testsfailed,
        )

    def pytest_unconfigure(self, config):
        os.close(self.fd)


def pytest_configure(config):
    directory = os.environ.get("OPENBEXI_SERVER_EVIDENCE_DIR")
    if directory:
        config.pluginmanager.register(
            QualificationJournal(Path(directory)), "openbexi-qualification-result-journal"
        )
