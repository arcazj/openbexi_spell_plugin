"""Real SQLite migration/reopening checks; native behavior has a separate oracle."""
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
sys.path.insert(0,str(ROOT/'driver_plugin/src'))
import rng_state_patches
from openbexi_spell_dss.journal import Journal

NAME='openbexi_spell_dss/ground.py'
URL='http://127.0.0.1:19001'
EPOCH='fixed-test-epoch'
NAMESPACE=hashlib.sha256((URL+'\0'+EPOCH).encode()).hexdigest()


def candidate():
    raw=(ROOT/'driver_plugin/src'/NAME).read_bytes()
    module=ModuleType('openbexi_spell_dss._rng_state_candidate')
    module.__package__ = 'openbexi_spell_dss'
    module.__package__='openbexi_spell_dss'
    exec(compile(rng_state_patches.apply(NAME,raw),NAME,'exec'),module.__dict__)
    return module.Ground


def seed(path,state):
    with JournalContext(path) as journal:
        journal.db.execute('CREATE TABLE ground(namespace TEXT PRIMARY KEY,state TEXT NOT NULL)')
        encoded=json.dumps(state,indent=1)
        journal.db.execute('INSERT INTO ground VALUES(?,?)',(NAMESPACE,encoded))
        journal.db.execute('INSERT INTO ground VALUES(?,?)',('unrelated-namespace',' { "untouched" : [1, 2] } '))
        return encoded


class JournalContext:
    def __init__(self,path): self.path=path
    def __enter__(self):
        self.journal=Journal(self.path)
        return self.journal
    def __exit__(self,*args): self.journal.close()


def reopen(path):
    with JournalContext(path) as journal:
        ground=candidate()(SimpleNamespace(url=URL,epoch=EPOCH),journal)
        encoded,=journal.db.execute('SELECT state FROM ground WHERE namespace=?',(NAMESPACE,)).fetchone()
        untouched,=journal.db.execute('SELECT state FROM ground WHERE namespace=?',('unrelated-namespace',)).fetchone()
        assert untouched==' { "untouched" : [1, 2] } '
        return ground.state(),encoded


@pytest.mark.parametrize('legacy,activity,schedule',[
    ('DISABLED','READY',False),('READY','READY',True),
    ('RANGING','RANGING',True),('CALIBRATING','CALIBRATING',True),
])
def test_legacy_migration_is_persistent_idempotent_and_preserves_other_data(tmp_path,legacy,activity,schedule):
    path=tmp_path/'ground.sqlite'
    state=dict(ranging=legacy,unrelated={'nested':[0,False,'caf\u00e9']},resources={'saved':42})
    seed(path,state)
    expected=dict(state,ranging=activity,ranging_schedule_enabled=schedule)
    first,encoded=reopen(path)
    assert first==expected
    second,again=reopen(path)
    assert second==expected and again==encoded


@pytest.mark.parametrize('activity',['READY','RANGING','CALIBRATING'])
@pytest.mark.parametrize('schedule',[False,True])
def test_explicit_schedule_and_new_state_survive_reopening_without_rewrite(tmp_path,activity,schedule):
    path=tmp_path/'ground.sqlite'
    state=dict(ranging=activity,ranging_schedule_enabled=schedule,unrelated=['retain',12])
    original=seed(path,state)
    assert reopen(path)==(state,original)
    assert reopen(path)==(state,original)


@pytest.mark.parametrize('state',[
    {'ranging':'UNKNOWN'}, {'ranging':[]}, {}, [],
    {'ranging':'RANGING','ranging_schedule_enabled':0},
    {'ranging':'CALIBRATING','ranging_schedule_enabled':'False'},
    {'ranging':'DISABLED','ranging_schedule_enabled':False},
])
def test_invalid_migration_fails_atomically_without_overwrite(tmp_path,state):
    path=tmp_path/'ground.sqlite'
    original=seed(path,state)
    with pytest.raises(ValueError): reopen(path)
    with JournalContext(path) as journal:
        actual,=journal.db.execute('SELECT state FROM ground WHERE namespace=?',(NAMESPACE,)).fetchone()
        assert actual==original
        assert dict(journal.db.execute('SELECT namespace,state FROM ground'))['unrelated-namespace']==' { "untouched" : [1, 2] } '


def test_patch_refuses_an_unreviewed_preimage():
    with pytest.raises(ValueError,match='Unexpected'):
        rng_state_patches.apply(NAME,b'different source')


def test_new_database_starts_idle_with_disabled_schedule_and_reopens(tmp_path):
    path=tmp_path/'new.sqlite'
    with JournalContext(path) as journal:
        ground=candidate()(SimpleNamespace(url=URL,epoch=EPOCH),journal)
        first=ground.state()
        assert first['ranging']=='READY'
        assert first['ranging_schedule_enabled'] is False
        assert journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
    with JournalContext(path) as journal:
        again=candidate()(SimpleNamespace(url=URL,epoch=EPOCH),journal)
        assert again.state()==first
