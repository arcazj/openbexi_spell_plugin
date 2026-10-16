"""Read-only evidence review must not change the captured file set."""
import hashlib
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'conformance'))
from evidence_database import evidence_database


def snapshot(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}


def test_checkpointed_wal_database_is_read_without_artifact_changes(tmp_path):
    path = tmp_path/'driver.sqlite'
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE effects (receipt BLOB)')
    db.execute("INSERT INTO effects VALUES (x'010203')")
    db.commit()
    db.close()
    before = snapshot(tmp_path)
    for _ in range(3):
        with evidence_database(path) as review:
            assert review.execute('SELECT receipt FROM effects').fetchall() == [(b'\x01\x02\x03',)]
            with pytest.raises(sqlite3.OperationalError):
                review.execute("INSERT INTO effects VALUES (x'04')")
        with pytest.raises(sqlite3.ProgrammingError):
            review.execute('SELECT 1')
        assert snapshot(tmp_path) == before


def test_uncheckpointed_wal_is_rejected_instead_of_losing_committed_rows(tmp_path):
    path = tmp_path/'driver.sqlite'
    db = sqlite3.connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE effects (receipt INTEGER)')
        db.execute('INSERT INTO effects VALUES (42)')
        db.commit()
        before = snapshot(tmp_path)
        with pytest.raises(ValueError, match='not checkpointed'):
            with evidence_database(path):
                pytest.fail('Uncheckpointed database was accepted')
        assert snapshot(tmp_path) == before
    finally:
        db.close()
