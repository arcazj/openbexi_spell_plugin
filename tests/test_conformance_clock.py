"""Exercise controller CAS handling with the real transactional simulator."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'conformance'))
from clock_step import try_step
from dss.engine import DssConflict, DssEngine
from dss.packets import encode_tc


def test_command_progress_rejects_stale_tick_then_fresh_tick_succeeds(tmp_path):
    engine = DssEngine(tmp_path/'dss.sqlite')
    try:
        before = engine.state()
        request = dict(schema_version='openbexi.dss.tc/1', satellite_id='GENERIC',
            database_revision=engine.catalog.revision, database_digest=engine.catalog.digest,
            satellite_epoch=before['epoch'], scenario_id=before['scenario_id'],
            operation_id='clock-race', procedure_id='test', execution_id='test', plan_id='plan',
            element_id='element', stage='TRANSPORT', command_name='CMD1', arguments=[], command_digest='a'*64)
        engine.process_tc(request, encode_tc(request))
        changed = engine.state()
        assert changed['revision'] > before['revision']
        accepted, rejected = [], []
        assert not try_step(engine, before, 'packet', [], accepted, rejected)
        assert engine.state() == changed and accepted == [] and len(rejected) == 1
        assert try_step(engine, changed, 'packet', ['TRANSPORT'], accepted, rejected)
        assert len(accepted) == 1 and accepted[0]['after'] == engine.state()
    finally:
        engine.close()


@pytest.mark.parametrize('cause', ['new-epoch', 'running'])
def test_authority_and_control_failures_are_not_retried(tmp_path, cause):
    engine = DssEngine(tmp_path/'dss.sqlite')
    try:
        before = engine.state()
        if cause == 'new-epoch':
            engine.reset('new-scenario', expected_epoch=before['epoch'])
        else:
            engine.control('RESUME', before['epoch'], before['revision'])
            before = engine.state()
        accepted, rejected = [], []
        with pytest.raises(DssConflict):
            try_step(engine, before, 'packet', [], accepted, rejected)
        assert accepted == rejected == []
    finally:
        engine.close()
