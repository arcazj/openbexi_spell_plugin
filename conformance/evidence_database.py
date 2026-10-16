"""Read a closed, checkpointed evidence database without creating sidecars."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3


@contextmanager
def evidence_database(path):
    path = Path(path).resolve(strict=True)
    # SQLite immutable mode ignores WAL contents. Reject uncheckpointed evidence
    # instead of silently reviewing an older main database snapshot.
    for suffix in ('-wal', '-journal'):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError('Evidence database is not checkpointed: ' + str(sidecar))
    db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        yield db
    finally:
        db.close()
