"""Authoritative sequence discovery through the original RPC, without reordering."""
from copy import deepcopy
import sys
import types

import grpc
import pytest

import test_command_rpc as rpc_tests
from test_command_rpc import p,g,pack,composed as scheduling_module
import command_catalog_patches
from dss.catalog import SatelliteDatabase
from openbexi_spell_dss.command_catalog import lookup
from openbexi_spell_dss.codec import unpack


@pytest.fixture
def bridge(tmp_path,monkeypatch):
    def composed(name):
        if name!='rpc':return scheduling_module(name)
        path='openbexi_spell_dss/rpc.py'
        raw=(rpc_tests.ROOT/'driver_plugin/src'/path).read_bytes()
        for recipe in rpc_tests.integrated_patches.DRIVER_RECIPES:
            if path in recipe.PREIMAGES:raw=recipe.apply(path,raw)
            if recipe is command_catalog_patches:break
        module=types.ModuleType('openbexi_spell_dss._catalog_rpc_test')
        exec(compile(raw,path,'exec'),module.__dict__)
        return module
    monkeypatch.setattr(rpc_tests,'composed',composed)
    yield from rpc_tests.bridge.__wrapped__(tmp_path,monkeypatch)


@pytest.mark.parametrize('name,members',[
    ('SEQNAME',['CMD1','CMD2','CMD3']),('SEQ.DUPLICATE',['CMD1','CMD1','CMD2'])])
def test_catalog_sequence_keeps_order_duplicates_and_independent_copy(name,members):
    database=SatelliteDatabase.load()
    row=lookup(database,name)
    assert row['kind']=='SEQUENCE' and [item['command'] for item in row['members']]==members
    row['members'][0]['args']['injected']='changed'
    assert lookup(database,name)['members'][0]['args']=={}


def test_unknown_sequence_and_ambiguous_catalog_are_rejected():
    database=SatelliteDatabase.load()
    with pytest.raises(ValueError):lookup(database,'NO_SUCH_SEQUENCE')
    database.material['command_sequences'].append(deepcopy(database.material['command_sequences'][0]))
    with pytest.raises(ValueError,match='ambiguous'):lookup(database,'SEQNAME')


@pytest.mark.parametrize('members',[[],[{'command':'CMD1','args':{},'modifiers':{}}]*17,
    [{'command':'SEQNAME','args':{},'modifiers':{}}],
    [{'command':'CMD1','args':[],'modifiers':{}}],
    [{'command':'CMD1','args':{},'modifiers':[]}],
    [{'command':'CMD1','args':{},'modifiers':{},'unknown':True}]])
def test_invalid_sequence_structure_cannot_be_presented_as_sendable(members):
    database=SatelliteDatabase.load()
    database.material['command_sequences'][0]['members']=members
    with pytest.raises(ValueError):lookup(database,'SEQNAME')


def test_original_rpc_discovers_both_sequence_and_member_definitions(bridge):
    for name in ('SEQNAME','SEQ.DUPLICATE'):
        row=bridge.stub.CreateTcItem(p.TcItemDesc(mnemonic=name),timeout=3)
        assert row.mnemonic==name and row.id=='SEQUENCE'
    # Invoke the exact original lookup message through its protobuf boundary.
    raw=p.LookupRequest(name='SEQ.DUPLICATE',source='GENERIC',type='TC').SerializeToString()
    result=p.LookupAnswer.FromString(bridge.dispatch('/spell.driver.SPELLDriverInterface_TM/DatabaseLookup',raw))
    definition=unpack(result.lookup)
    assert [row['command'] for row in definition['members']]==['CMD1','CMD1','CMD2']
    raw=p.LookupRequest(name='TC.SIMULATOR.RESET',source='GENERIC',type='TC').SerializeToString()
    result=p.LookupAnswer.FromString(bridge.dispatch('/spell.driver.SPELLDriverInterface_TM/DatabaseLookup',raw))
    assert unpack(result.lookup)['critical'] is True
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
    assert bridge.engine.state()['core']['commands_executed']==0


def test_unknown_sequence_rpc_has_no_effect(bridge):
    with pytest.raises(grpc.RpcError) as error:
        bridge.stub.CreateTcItem(p.TcItemDesc(mnemonic='SEQ.UNKNOWN'),timeout=3)
    assert error.value.code()==grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
