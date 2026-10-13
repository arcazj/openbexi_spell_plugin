"""Durable effect intent/receipt pairing. Pending intents are never replayed."""
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time


class UncertainEffect(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def authority(value):
    keys = {'session', 'procedure', 'definition', 'version', 'controller_epoch',
            'procedure_fence', 'mode', 'release'}
    if type(value) is not dict or set(value) != keys:
        raise ValueError('Incomplete driver authority')
    for key in ('session', 'procedure'):
        if type(value[key]) is not str or re.fullmatch('[0-9a-f]{32}', value[key]) is None:
            raise ValueError('Invalid driver run identity')
    for key in ('definition', 'version'):
        if type(value[key]) is not str or not 1 <= len(value[key]) <= 512:
            raise ValueError('Invalid driver source identity')
    for key in ('controller_epoch', 'procedure_fence'):
        if type(value[key]) is not int or value[key] < 1:
            raise ValueError('Invalid driver fence')
    if value['mode'] not in {'Development', 'Monitoring', 'Execution'}:
        raise ValueError('Invalid driver operating mode')
    if value['mode'] == 'Execution':
        if type(value['release']) is not str or re.fullmatch('[0-9a-f]{64}', value['release']) is None:
            raise ValueError('Execution requires an immutable release identity')
    elif value['release'] is not None:
        raise ValueError('Unexpected release identity')
    return canonical(value)


class Journal:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=5)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS fences(session TEXT, definition TEXT, fence INTEGER NOT NULL,
              epoch INTEGER NOT NULL, PRIMARY KEY(session, definition));
            CREATE TABLE IF NOT EXISTS effects(session TEXT, procedure TEXT, request_id TEXT,
              authority TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL,
              receipt BLOB, created_ns INTEGER NOT NULL,
              PRIMARY KEY(session, procedure, request_id));
            CREATE TABLE IF NOT EXISTS events(session TEXT, procedure TEXT, request_id TEXT,
              message TEXT NOT NULL, severity INTEGER NOT NULL, scope INTEGER NOT NULL,
              created_ns INTEGER NOT NULL, PRIMARY KEY(session,procedure,request_id));
        ''')

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK')
                raise

    def begin(self, identity, request_id, method, payload):
        binding = authority(identity)
        if identity['mode'] == 'Monitoring':
            raise PermissionError('Monitoring cannot perform driver effects')
        if (type(request_id) is not str or re.fullmatch('[0-9a-f]{32}', request_id) is None
                or type(payload) is not bytes or len(payload) > 65536
                or type(method) is not str or not 1 <= len(method) <= 128):
            raise ValueError('Invalid driver effect request')
        digest = hashlib.sha256(method.encode() + b'\0' + payload).hexdigest()
        run = identity['session'], identity['procedure'], request_id
        fence_key = identity['session'], identity['definition']
        fence, epoch = identity['procedure_fence'], identity['controller_epoch']
        with self.transaction():
            row = self.db.execute('SELECT fence,epoch FROM fences WHERE session=? AND definition=?', fence_key).fetchone()
            if row and (fence < row[0] or epoch < row[1]):
                raise PermissionError('Stale driver authority')
            self.db.execute('INSERT INTO fences VALUES(?,?,?,?) ON CONFLICT(session,definition) DO UPDATE SET fence=excluded.fence,epoch=excluded.epoch', (*fence_key, fence, epoch))
            row = self.db.execute('SELECT authority,digest,state,receipt FROM effects WHERE session=? AND procedure=? AND request_id=?', run).fetchone()
            if row:
                if row[:2] != (binding, digest):
                    raise PermissionError('Driver request identity was reused with different authority or content')
                if row[2] != 'RECEIPTED':
                    raise UncertainEffect('Driver effect has no definitive receipt; reconcile without replay')
                return row[3]
            if self.db.execute("SELECT 1 FROM effects WHERE session=? AND procedure=? AND state!='RECEIPTED' LIMIT 1", run[:2]).fetchone():
                raise UncertainEffect('This run has an unresolved driver effect')
            self.db.execute('INSERT INTO effects VALUES(?,?,?,?,?,?,?,?)',
                            (*run, binding, digest, 'PENDING', None, time.time_ns()))
        return None

    def finish(self, identity, request_id, receipt):
        binding = authority(identity)
        if type(receipt) is not bytes or len(receipt) > 65536:
            raise ValueError('Invalid driver receipt')
        with self.transaction():
            count = self.db.execute("UPDATE effects SET state='RECEIPTED',receipt=? WHERE session=? AND procedure=? AND request_id=? AND authority=? AND state='PENDING'",
                (receipt, identity['session'], identity['procedure'], request_id, binding)).rowcount
            if count != 1:
                raise UncertainEffect('Driver receipt has no matching pending intent')

    def close(self):
        with self.lock:
            self.db.close()

    def event(self,identity,request_id,message,severity,scope):
        with self.transaction():
            run = identity['session'],identity['procedure']
            if self.db.execute('SELECT count(*) FROM events WHERE session=? AND procedure=?',run).fetchone()[0] >= 4096:
                raise ValueError('Driver event journal run bound exceeded')
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',
                            (*run,request_id,message,severity,scope,time.time_ns()))
