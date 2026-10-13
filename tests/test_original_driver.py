"""Original protobuf RPC -> actual DSS binary TCP, plus independent failure oracles."""
from contextlib import contextmanager
import json
import hashlib
import threading
import uuid
import grpc
import pytest
from google.protobuf.any_pb2 import Any
from google.protobuf.empty_pb2 import Empty
from google.protobuf.wrappers_pb2 import DoubleValue
from dss.local import create_servers
from dss.packets import encode_tm
from openbexi_spell_dss.codec import pack, unpack, Time
from openbexi_spell_dss.journal import Journal, UncertainEffect
from openbexi_spell_dss.rpc import Dispatcher, PREFIX
from openbexi_spell_dss.server import Server
from openbexi_spell_dss.transport import Transport
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p, SPELLDriver_pb2_grpc as g


def identity():
    return dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex, definition='test-procedure',
                version='a'*64, controller_epoch=1, procedure_fence=1, mode='Development', release=None)


@pytest.fixture
def bridge(tmp_path):
    runtime, tcp, http = create_servers(tmp_path/'dss.sqlite', 0)
    threads = [threading.Thread(target=server.serve_forever) for server in (tcp,http)]
    for thread in threads:
        thread.start()
    transport = Transport('http://127.0.0.1:' + str(http.server_port), tcp.server_address)
    journal = Journal(tmp_path/'effects.sqlite')
    dispatcher = Dispatcher(transport,journal,users={'qualification':hashlib.sha256(b'simulator-only').hexdigest()})
    who = identity()
    calls = []
    def check():
        calls.append(True)
    def dispatch(path, raw):
        return dispatcher.dispatch(path,raw,who,uuid.uuid4().hex,check)
    server = Server(dispatch)
    channel = grpc.insecure_channel('127.0.0.1:' + str(server.port))
    try:
        yield runtime,transport,journal,dispatcher,who,calls,channel
    finally:
        channel.close()
        server.close()
        transport.close()
        journal.close()
        for service in (http,tcp):
            service.shutdown()
            service.server_close()
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
        runtime.engine.close()


@pytest.mark.parametrize('value',[None,True,False,0,-2,2**63-1,1.25,'text',b'bytes',
                                {'Wait':True,'Timeout':1.5},[1,'x',None],Time('2026-001/00:00:00')])
def test_original_any_shapes_round_trip(value):
    assert unpack(pack(value)) == value


def test_codec_rejects_ambiguous_and_nonfinite_values():
    duplicate = p.Dict()
    for _ in range(2):
        duplicate.entries.add(key=pack('x'),value=pack(1))
    raw = Any()
    raw.Pack(duplicate)
    with pytest.raises(ValueError,match='Duplicate'):
        unpack(raw)
    raw.Pack(DoubleValue(value=float('nan')))
    with pytest.raises(ValueError,match='Nonfinite'):
        unpack(raw)
    with pytest.raises(ValueError):
        pack('a'*8193)
    nested = None
    for _ in range(14):
        nested = [nested]
    with pytest.raises(ValueError):
        pack(nested)


def test_real_rpc_tc_changes_dss_once_and_has_five_binary_receipts(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    result = g.SPELLDriverInterface_TCStub(channel).SendCommand(
        p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1'),args=pack([]),config=pack({})),timeout=5)
    assert result.value is True
    state = runtime.engine.state()
    assert state['core']['commands_executed'] == 1
    evidence = runtime.engine.evidence(state['scenario_id'])
    assert [r['acknowledgement']['stage'] for r in evidence['operations']] == [
        'TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT','ONBOARD_EXECUTION']
    assert all(row['ingress_delivery_count'] == 1 for row in evidence['operations'])
    assert len(calls) == 7
    assert journal.db.execute('SELECT state FROM effects').fetchall() == [('RECEIPTED',)]


def test_real_rpc_tm_value_validity_and_time(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    name = transport.database.telemetry[0]['item_id']
    stub = g.SPELLDriverInterface_TMStub(channel)
    item = stub.CreateTmItem(p.TmItemDesc(mnemonic=name),timeout=3)
    actual = stub.RefreshItem(p.TmItemValue(item=item,config=pack({})),timeout=3)
    expected = runtime.engine.telemetry()['samples'][0]
    assert actual.validity is True
    assert unpack(actual.rawValue) == expected['raw']['value']
    assert unpack(actual.engValue) == expected['engineering']['value']
    assert actual.timestamp
    utc = g.SPELLDriverInterface_TIMEStub(channel).GetUTC(pack({}),timeout=3)
    assert utc.timeMsg


def test_monitoring_rejects_command_before_any_network_effect(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    who['mode'] = 'Monitoring'
    with pytest.raises(grpc.RpcError) as error:
        g.SPELLDriverInterface_TCStub(channel).SendCommand(p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1')),timeout=3)
    assert error.value.code() == grpc.StatusCode.PERMISSION_DENIED
    assert runtime.engine.state()['core']['commands_executed'] == 0
    assert journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0


def test_deduplicated_receipt_and_stale_fence_rejection(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    path = '/' + PREFIX + '_TC/SendCommand'
    raw = p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1')).SerializeToString()
    request = uuid.uuid4().hex
    first = dispatcher.dispatch(path,raw,who,request,lambda:None)
    assert dispatcher.dispatch(path,raw,who,request,lambda:None) == first
    assert runtime.engine.state()['core']['commands_executed'] == 1
    newer = dict(who,controller_epoch=2)
    dispatcher.dispatch(path,raw,newer,uuid.uuid4().hex,lambda:None)
    with pytest.raises(PermissionError,match='Stale'):
        dispatcher.dispatch(path,raw,who,uuid.uuid4().hex,lambda:None)


def test_lost_release_ack_holds_run_across_journal_reopen(bridge,tmp_path):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    old = runtime.engine.state()
    runtime.engine.reset('lost-ack', faults={'lost_ack':True}, expected_epoch=old['epoch'])
    state = runtime.engine.state()
    transport.epoch, transport.scenario = state['epoch'],state['scenario_id']
    raw = p.CommandDesc(command=p.TcItemDesc(mnemonic='CMD1')).SerializeToString()
    path, request = '/' + PREFIX + '_TC/SendCommand', uuid.uuid4().hex
    with pytest.raises(UncertainEffect):
        dispatcher.dispatch(path,raw,who,request,lambda:None)
    assert runtime.engine.state()['core']['commands_executed'] == 1
    reopened = Journal(tmp_path/'effects.sqlite')
    try:
        for request_id in (request,uuid.uuid4().hex):
            with pytest.raises(UncertainEffect):
                Dispatcher(transport,reopened).dispatch(path,raw,who,request_id,lambda:None)
    finally:
        reopened.close()
    assert runtime.engine.state()['core']['commands_executed'] == 1


def test_telemetry_duplicates_conflicts_and_freshness_timeout(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    raw = bytes.fromhex(runtime.engine.telemetry()['packet_hex'])
    assert transport.telemetry.accept(raw)
    assert not transport.telemetry.accept(raw)
    body = dict(transport.telemetry.body, cause_command='conflicting')
    with pytest.raises(ValueError,match='different bytes'):
        transport.telemetry.accept(encode_tm(body,body['tm_sequence'] & 0x3fff))
    with pytest.raises(TimeoutError):
        transport.sample(transport.database.telemetry[0]['item_id'],wait=True,timeout=.05)


def test_pending_effect_recovered_without_callback(tmp_path):
    path,who,request = tmp_path/'journal.sqlite',identity(),uuid.uuid4().hex
    journal = Journal(path)
    assert journal.begin(who,request,'method',b'payload') is None
    journal.close()
    recovered = Journal(path)
    try:
        with pytest.raises(UncertainEffect):
            recovered.begin(who,request,'method',b'payload')
    finally:
        recovered.close()


def test_all_service_families_have_truthful_simulator_behavior(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    info = g.SPELLDriverInterfaceStub(channel).GetDriverInfo(p.DriverInfo(),timeout=3)
    assert set(info.interfaces) == set(range(9)) | {10}
    g.SPELLDriverInterface_EVStub(channel).RaiseEvent(p.Event(message='family qualification',config=pack({'Severity':8,'Scope':1})),timeout=3)
    assert journal.db.execute('SELECT message,severity,scope FROM events').fetchall() == [('family qualification',8,1)]
    resources = g.SPELLDriverInterface_RSCStub(channel)
    assert resources.SetResource(p.ResourceRequest(name='setpoint',value=pack(12)),timeout=3).value
    assert unpack(resources.GetResource(p.ResourceRequest(name='setpoint'),timeout=3).value) == 12
    assert resources.SetLink(p.LinkRequest(name='TC',status=False),timeout=3).value
    assert not resources.CheckLink(p.LinkRequest(name='TC'),timeout=3).value
    assert resources.SetLink(p.LinkRequest(name='TC',status=True),timeout=3).value
    tasks = g.SPELLDriverInterface_TASKStub(channel)
    with pytest.raises(grpc.RpcError) as rejected:
        tasks.StartTask(p.Task(name='DSS_CLOCK'),timeout=3)
    assert rejected.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert tasks.CheckTask(p.Task(name='DSS_CLOCK'),timeout=3).value == 0
    assert tasks.StopTask(p.Task(name='DSS_CLOCK'),timeout=3).value
    assert runtime.engine.state()['running'] is False
    tasks.OpenDisplay(p.Display(name='DSS_TELEMETRY'),timeout=3)
    tasks.PrintDisplay(p.Display(name='DSS_TELEMETRY'),timeout=3)
    tasks.CloseDisplay(p.Display(name='DSS_TELEMETRY'),timeout=3)
    assert 'display-DSS_TELEMETRY' in dispatcher.ground.state()['reports']
    memory = g.SPELLDriverInterface_MEMStub(channel)
    assert memory.CreateGoldenImage(p.GoldenImageRequest(scp='GENERIC',filename='before'),timeout=3).value
    image = unpack(memory.MemoryLookup(p.MemoryLookupRequest(name='DSS_STATE',image='before'),timeout=3))
    assert image['epoch'] == runtime.engine.state()['epoch']
    assert memory.GenerateReport(p.MemoryReportRequest(image='before'),timeout=3).value
    assert memory.CompareImages(p.CompareMemoryReportRequest(image1='before',image2='before'),timeout=3).value
    user = g.SPELLDriverInterface_USERStub(channel)
    assert not user.IsLoggedIn(p.LoginCred(username='qualification'),timeout=3).value
    assert user.Login(p.LoginCred(username='qualification',password='simulator-only'),timeout=3).value
    assert user.IsLoggedIn(p.LoginCred(username='qualification'),timeout=3).value
    assert user.Logout(p.LoginCred(username='qualification'),timeout=3).value
    ranging = g.SPELLDriverInterface_RNGStub(channel)
    assert list(ranging.GetBasebandNames(pack({}),timeout=3).names) == ['DSS-BBE-1']
    path = p.Ranging(bbe='DSS-BBE-1',antenna='DSS-ANTENNA-1')
    assert not ranging.StartRanging(path,timeout=3).value
    assert ranging.EnableRanging(p.Ranging(),timeout=3).value
    assert ranging.StartRanging(path,timeout=3).value
    assert ranging.GetRangingStatus(pack({}),timeout=3).value == 'RANGING'
    assert ranging.AbortRanging(p.Ranging(),timeout=3).value
    pcs = g.SPELLDriverInterface_PCSStub(channel)
    assert pcs.PCS_ReadyToCommand(pack({}),timeout=3).value == 'READY'
    result = pcs.SendPtcCommand(p.PtcDesc(command=p.PtcItemDesc(mnemonic='CMD1'),args=pack([])),timeout=5)
    assert list(result.success) == [True]
    assert runtime.engine.state()['core']['commands_executed'] == 1
    assert g.SPELLDriverInterface_TIMEStub(channel).GetUTC(pack({}),timeout=3).timeMsg


def test_ground_failures_do_not_turn_into_success_or_effects(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    requests = [
        (g.SPELLDriverInterface_RNGStub(channel).UpdateCortexConf,pack({}),grpc.StatusCode.UNIMPLEMENTED),
        (g.SPELLDriverInterface_TASKStub(channel).StartTask,p.Task(name='arbitrary-shell'),grpc.StatusCode.INVALID_ARGUMENT),
        (g.SPELLDriverInterface_USERStub(channel).Login,p.LoginCred(username='qualification',password='wrong'),grpc.StatusCode.PERMISSION_DENIED),
        (g.SPELLDriverInterface_MEMStub(channel).CreateGoldenImage,p.GoldenImageRequest(scp='GENERIC',filename='../outside'),grpc.StatusCode.INVALID_ARGUMENT),
        (g.SPELLDriverInterface_PCSStub(channel).PCS_Control,p.PtcDesc(),grpc.StatusCode.UNIMPLEMENTED)]
    for method,value,status in requests:
        with pytest.raises(grpc.RpcError) as error:
            method(value,timeout=3)
        assert error.value.code() == status
    assert journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0
    assert runtime.engine.state()['core']['commands_executed'] == 0


def test_numeric_limits_injection_and_monitoring_mutation_rejection(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    tm = g.SPELLDriverInterface_TMStub(channel)
    item = p.TmItemDesc(mnemonic=transport.database.telemetry[0]['item_id'])
    limits = dict(LoRed=-100,LoYel=-50,HiYel=50,HiRed=100)
    assert tm.SetLimits(p.LimitSetRequest(item=item,set=p.LimitSet(limitset=pack(limits))),timeout=3).value
    assert unpack(tm.GetLimits(p.TmItemValue(item=item),timeout=3).limitset) == limits
    expected = 12 * transport.database.item(item.mnemonic)['engineering_scale']
    assert tm.InjectItem(p.TmItemValue(item=item,rawValue=pack(12),engValue=pack(expected),validity=True,timestamp='2026-10-12 00:00:00'),timeout=3).value
    value = tm.RefreshItem(p.TmItemValue(item=item),timeout=3)
    assert unpack(value.rawValue) == 12 and unpack(value.engValue) == expected
    who['mode'] = 'Monitoring'
    with pytest.raises(grpc.RpcError) as error:
        tm.RestoreNormalLimits(pack({}),timeout=3)
    assert error.value.code() == grpc.StatusCode.PERMISSION_DENIED
    assert unpack(tm.GetLimits(p.TmItemValue(item=item),timeout=3).limitset) == limits


def test_typed_radix_arguments_and_invalid_catalog_values(bridge):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    stub = g.SPELLDriverInterface_TCStub(channel)
    args = [['ARG1',1.25,{'ValueType':'float'}],['ARG2',16,{'ValueType':'long','Radix':'hex','ValueFormat':'Raw format'}]]
    assert stub.SendCommand(p.CommandDesc(command=p.TcItemDesc(mnemonic='TCNAME'),args=pack(args)),timeout=5).value
    state = runtime.engine.state()
    rows = runtime.engine.evidence(state['scenario_id'])['operations']
    assert rows[0]['acknowledgement']['command_name'] == 'TCNAME'
    for value in (True,-1,65536,'16'):
        args[1][1] = value
        with pytest.raises(grpc.RpcError):
            stub.SendCommand(p.CommandDesc(command=p.TcItemDesc(mnemonic='TCNAME'),args=pack(args)),timeout=5)
    assert runtime.engine.state()['core']['commands_executed'] == 1
    assert journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 1


@pytest.mark.parametrize('fault',[{'stale':True},{'source_gap':True},{'telemetry_quality':'BAD'}])
def test_stale_gapped_or_bad_telemetry_cannot_be_valid(bridge,fault):
    runtime,old,journal,dispatcher,who,calls,channel = bridge
    runtime.engine.reset('invalid-tm',faults=fault,expected_epoch=old.epoch)
    transport = Transport(old.url,old.tc_address)
    try:
        new = Dispatcher(transport,journal)
        item = p.TmItemDesc(mnemonic=transport.database.telemetry[0]['item_id'])
        raw = new.dispatch('/'+PREFIX+'_TM/RefreshItem',p.TmItemValue(item=item).SerializeToString(),who,uuid.uuid4().hex,lambda:None)
        assert not p.TmItemValue.FromString(raw).validity
    finally:
        transport.close()


def test_driver_ground_state_survives_restart_without_replaying_effects(bridge,tmp_path):
    runtime,transport,journal,dispatcher,who,calls,channel = bridge
    stub = g.SPELLDriverInterface_RSCStub(channel)
    assert stub.SetResource(p.ResourceRequest(name='retained',value=pack({'value':7})),timeout=3).value
    reopened = Journal(tmp_path/'effects.sqlite')
    try:
        recovered = Dispatcher(transport,reopened)
        assert recovered.ground.state()['resources']['retained'] == {'value':7}
        assert reopened.db.execute("SELECT state FROM effects").fetchall() == [('RECEIPTED',)]
    finally:
        reopened.close()
