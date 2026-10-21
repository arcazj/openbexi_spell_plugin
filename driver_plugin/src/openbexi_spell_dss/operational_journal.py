"""Operational admission bounds layered on the unchanged composed journal.

SQLite triggers reserve receipt space in the same transaction as each intent.
They also protect connections opened by legacy code after this offline upgrade.
No receipt, unresolved intent or fence is deleted to make room.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import sqlite3

from .journal import Journal as BaseJournal, UncertainEffect


class CapacityExceeded(RuntimeError):
    """Admission failed before a new external effect was started."""


class Journal(BaseJournal):
    def __init__(self, path, *, max_effects=100000, max_effects_per_run=16384,
                 max_bytes=64 * 1024 * 1024, max_events=100000):
        for value, ceiling in ((max_effects, 1000000), (max_effects_per_run, 1000000),
                               (max_bytes, 1024 * 1024 * 1024), (max_events, 1000000)):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError('Invalid driver journal capacity')
        if max_bytes < 131072:
            raise ValueError('Driver journal byte capacity must reserve a complete receipt')
        super().__init__(path)
        try:
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS journal_budget(kind TEXT PRIMARY KEY, entries INTEGER NOT NULL, bytes INTEGER NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS journal_limits(kind TEXT PRIMARY KEY, maximum INTEGER NOT NULL, per_run INTEGER NOT NULL, bytes INTEGER NOT NULL)')
                for row in [('effects', max_effects, min(max_effects_per_run, max_effects), max_bytes),
                            ('events', max_events, 4096, max_bytes)]:
                    self.db.execute('INSERT INTO journal_limits VALUES(?,?,?,?) ON CONFLICT(kind) DO UPDATE SET maximum=excluded.maximum,per_run=excluded.per_run,bytes=excluded.bytes', row)
                self.db.execute('''INSERT OR IGNORE INTO journal_budget
                    SELECT 'effects', COUNT(*), COALESCE(SUM(length(CAST(authority AS BLOB))+256+
                    CASE WHEN state='PENDING' THEN 65536 ELSE length(receipt) END),0) FROM effects''')
                self.db.execute('''INSERT OR IGNORE INTO journal_budget
                    SELECT 'events', COUNT(*), COALESCE(SUM(length(CAST(message AS BLOB))+256),0) FROM events''')
            # CREATE TRIGGER is idempotent and does not rewrite any legacy row.
            self.db.executescript('''
                CREATE TRIGGER IF NOT EXISTS operational_effect_admit BEFORE INSERT ON effects BEGIN
                  SELECT CASE WHEN
                    (SELECT entries FROM journal_budget WHERE kind='effects') >=
                    (SELECT maximum FROM journal_limits WHERE kind='effects') OR
                    (SELECT COUNT(*) FROM effects WHERE session=NEW.session AND procedure=NEW.procedure) >=
                    (SELECT per_run FROM journal_limits WHERE kind='effects') OR
                    (SELECT bytes FROM journal_budget WHERE kind='effects')+length(CAST(NEW.authority AS BLOB))+256+65536 >
                    (SELECT bytes FROM journal_limits WHERE kind='effects')
                    THEN RAISE(ABORT, 'OPERATIONAL_CAPACITY') END;
                  UPDATE journal_budget SET entries=entries+1,bytes=bytes+length(CAST(NEW.authority AS BLOB))+256+65536 WHERE kind='effects';
                END;
                CREATE TRIGGER IF NOT EXISTS operational_effect_receipt AFTER UPDATE OF state ON effects
                WHEN OLD.state='PENDING' AND NEW.state='RECEIPTED' BEGIN
                  UPDATE journal_budget SET bytes=bytes-65536+length(NEW.receipt) WHERE kind='effects';
                END;
                CREATE TRIGGER IF NOT EXISTS operational_event_admit BEFORE INSERT ON events BEGIN
                  SELECT CASE WHEN
                    (SELECT entries FROM journal_budget WHERE kind='events') >=
                    (SELECT maximum FROM journal_limits WHERE kind='events') OR
                    (SELECT bytes FROM journal_budget WHERE kind='events')+length(CAST(NEW.message AS BLOB))+256 >
                    (SELECT bytes FROM journal_limits WHERE kind='events')
                    THEN RAISE(ABORT, 'OPERATIONAL_CAPACITY') END;
                  UPDATE journal_budget SET entries=entries+1,bytes=bytes+length(CAST(NEW.message AS BLOB))+256 WHERE kind='events';
                END;
            ''')
        except BaseException:
            self.close()
            raise

    def usage(self):
        with self.lock:
            return {kind: dict(entries=entries, reserved_bytes=size)
                    for kind, entries, size in self.db.execute('SELECT kind,entries,bytes FROM journal_budget ORDER BY kind')}

    def begin(self, *args, **kwargs):
        try:
            return super().begin(*args, **kwargs)
        except sqlite3.IntegrityError as error:
            if str(error) != 'OPERATIONAL_CAPACITY':
                raise
            raise CapacityExceeded('Driver journal capacity reached; archive and provision a new authority') from error

    def event(self, *args, **kwargs):
        try:
            return super().event(*args, **kwargs)
        except sqlite3.IntegrityError as error:
            if str(error) != 'OPERATIONAL_CAPACITY':
                raise
            raise CapacityExceeded('Driver event journal capacity reached') from error
        except ValueError as error:
            if str(error) != 'Driver event journal run bound exceeded':
                raise
            raise CapacityExceeded('Driver event run capacity reached') from error
