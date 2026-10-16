"""Real protobuf/DSS tests of the proposed display backend, before native promotion."""
from pathlib import Path
import hashlib
import importlib
import json
import sys
import threading
import time
import types
import uuid
from xml.etree import ElementTree

import grpc
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'driver_plugin/src'))
sys.path.insert(0, str(ROOT / 'source_port'))
import display_patches
import integrated_patches
import patches
from zipfile import ZipFile
from dss.local import create_servers
from openbexi_spell_dss.codec import pack
from openbexi_spell_dss.displays import document, screen, snapshot_for, MAX_INSTANCES, MAX_JOBS
from openbexi_spell_dss.server import Server
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p, SPELLDriver_pb2_grpc as g
from openbexi_spell_dss.transport import Transport


def original(name):
    if name.startswith('spell/'):
        with ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
            raw = patches.apply(name, archive.read('src/spell/' + name))
        recipes = integrated_patches.PYTHON_RECIPES
    else:
        raw = (ROOT / 'driver_plugin/src' / name).read_bytes()
        recipes = integrated_patches.DRIVER_RECIPES
    for recipe in recipes:
        if recipe is display_patches:
            break  # This fixture verifies the exact pre-display source contract.
        if name in recipe.PREIMAGES:
            raw = recipe.apply(name, raw)
    return raw


def module(name):
    unit = types.ModuleType('openbexi_spell_dss._display_test_' + name)
    exec(compile(display_patches.apply('openbexi_spell_dss/' + name + '.py',
                 original('openbexi_spell_dss/' + name + '.py')), name + '.py', 'exec'), unit.__dict__)
    return unit


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    journal_type = module('journal').Journal
    ground_module = module('ground')
    monkeypatch.setitem(sys.modules, 'openbexi_spell_dss.ground', ground_module)
    dispatcher_type = module('rpc').Dispatcher
    runtime, tcp, http = create_servers(tmp_path / 'dss.sqlite', 0)
    threads = [threading.Thread(target=server.serve_forever) for server in (tcp, http)]
    for thread in threads:
        thread.start()
    transport = Transport('http://127.0.0.1:' + str(http.server_port), tcp.server_address)
    journal = journal_type(tmp_path / 'effects.sqlite')
    dispatcher = dispatcher_type(transport, journal)
    who = dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex, definition='displays',
               version='candidate', controller_epoch=1, procedure_fence=1, mode='Development', release=None)
    request_id = [None]
    def dispatch(path, raw):
        return dispatcher.dispatch(path, raw, who, request_id[0] or uuid.uuid4().hex, lambda: None)
    server = Server(dispatch)
    channel = grpc.insecure_channel('127.0.0.1:' + str(server.port))
    stub = g.SPELLDriverInterface_TASKStub(channel)
    def call(method, name='DSS_TELEMETRY', **options):
        return getattr(stub, method)(p.Display(name=name, config=pack(options)), timeout=5)
    env = types.SimpleNamespace(call=call, ground=dispatcher.ground, journal=journal, who=who,
        request_id=request_id, runtime=runtime, transport=transport, journal_type=journal_type,
        ground_type=ground_module.Ground, path=tmp_path / 'effects.sqlite')
    try:
        yield env
    finally:
        channel.close()
        server.close()
        transport.close()
        journal.close()
        for service in (http, tcp):
            service.shutdown()
            service.server_close()
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
        runtime.engine.close()


def applications(env):
    return env.ground.state()['display_applications']


def test_workspace_is_one_application_and_close_preserves_other_host(bridge):
    bridge.call('OpenDisplay', 'DSS_WORKSPACE', _OpenBEXIWorkspace=True)
    app, = applications(bridge).values()
    assert app['host'] == 'DSS' and app['monitor'] == 1
    assert set(app['displays']) == {'DSS_TELEMETRY', 'DSS_TREND'}
    assert app['workspaces'] == {'DSS_WORKSPACE': ['DSS_TELEMETRY', 'DSS_TREND']}
    bridge.call('OpenDisplay', Host='DSS_AUX', Monitor=2)
    bridge.call('CloseDisplay', 'DSS_WORKSPACE', _OpenBEXIWorkspace=True)
    app, = applications(bridge).values()
    assert app['host'] == 'DSS_AUX' and app['monitor'] == 2
    bridge.call('CloseDisplay', Host='DSS_AUX')
    assert applications(bridge) == {}


def test_reuse_and_new_instances_have_distinct_routes(bridge):
    bridge.call('OpenDisplay', Monitor=2)
    first = applications(bridge)
    bridge.call('OpenDisplay', 'DSS_TREND', Monitor=2, Reuse=True, Time=3600)
    assert set(applications(bridge)) == set(first)
    app, = applications(bridge).values()
    assert set(app['displays']) == {'DSS_TELEMETRY', 'DSS_TREND'}
    assert app['displays']['DSS_TREND']['span_seconds'] == 3600
    bridge.call('OpenDisplay', Reuse=False, Monitor=2)
    bridge.call('OpenDisplay', Monitor=1)
    bridge.call('OpenDisplay', Host='DSS_AUX', Monitor=2)
    assert len(applications(bridge)) == 4
    bridge.call('CloseDisplay', Host='DSS')
    assert len(applications(bridge)) == 2
    assert sum('DSS_TELEMETRY' in app['displays'] for app in applications(bridge).values()) == 1


def test_unicode_names_html_and_plot_time_axis_are_real(bridge):
    bridge.call('OpenDisplay', 'Workspaces/Operación', _OpenBEXIWorkspace=True)
    bridge.call('OpenDisplay', 'DSS_TREND', Time=.25)
    state = bridge.ground.state()
    html = document(state)
    assert 'Displays/Telemetría' in html and '<table>' in html and '<svg ' in html
    app, = applications(bridge).values()
    record = app['displays']['DSS_TREND']
    element = ElementTree.fromstring(screen('DSS_TREND', record, state))
    labels = [row.text for row in element.iter('{http://www.w3.org/2000/svg}text')]
    from datetime import datetime
    assert (datetime.fromisoformat(labels[1]) - datetime.fromisoformat(labels[0])).total_seconds() == .25
    assert snapshot_for(record, state)['samples'] == bridge.runtime.engine.telemetry()['samples']
    assert '<circle ' in html


def test_ps_and_vector_are_documents_with_acquired_values_and_spool_routes(bridge):
    bridge.call('OpenDisplay', 'Displays/Telemetría')
    bridge.call('PrintDisplay', 'Displays/Telemetría', Format='VECTOR')
    bridge.call('PrintDisplay', 'Displays/Telemetría', Format='PS', Printer='DSS_REPORTS')
    jobs = list(bridge.ground.state()['display_jobs'].values())
    assert len(jobs) == 2
    vector, ps = jobs
    assert vector['status'] == 'FILE' and not vector['printer']
    assert vector['content'].isascii() and 'Telemetr\\xeda' in vector['content']
    assert vector['content'].startswith('DISPLAY\t')
    assert ps['status'] == 'SPOOLED' and ps['printer'] == 'DSS_REPORTS'
    assert ps['content'].startswith('%!PS-Adobe-3.0\n')
    assert '%%Page: 1 1\n' in ps['content'] and ps['content'].endswith('%%EOF\n')
    assert ps['content'].count('showpage') >= 1
    for row in bridge.runtime.engine.telemetry()['samples']:
        assert row['item_id'] in vector['content']
        assert str(row['engineering']['value']) in vector['content']


def test_plot_postscript_preserves_selected_instance_time_span(bridge):
    bridge.call('OpenDisplay', 'DSS_TREND', Time=1)
    bridge.call('OpenDisplay', 'DSS_TREND', Time=3600, Reuse=False)
    bridge.call('PrintDisplay', 'DSS_TREND', Format='PS')
    job, = bridge.ground.state()['display_jobs'].values()
    assert job['application'] == '2' and job['span_seconds'] == 3600
    assert 'Initial time span: 3600.000000 seconds' in job['content']
    assert 'arc fill' in job['content'] and 'lineto stroke' in job['content']


@pytest.mark.parametrize('method,name,options', [
    ('OpenDisplay', 'missing', {}),
    ('OpenDisplay', 'DSS_TELEMETRY', {'Host': '../host'}),
    ('OpenDisplay', 'DSS_TELEMETRY', {'Monitor': True}),
    ('OpenDisplay', 'DSS_TELEMETRY', {'Monitor': 0}),
    ('OpenDisplay', 'DSS_TELEMETRY', {'Reuse': 1}),
    ('OpenDisplay', 'DSS_TELEMETRY', {'Time': 1}),
    ('OpenDisplay', 'DSS_TREND', {'Time': 0}),
    ('OpenDisplay', 'DSS_TREND', {'Time': 86400.01}),
    ('OpenDisplay', 'DSS_WORKSPACE', {'_OpenBEXIWorkspace': True, 'Time': 1}),
    ('PrintDisplay', 'DSS_WORKSPACE', {'_OpenBEXIWorkspace': True}),
    ('PrintDisplay', 'DSS_TELEMETRY', {'Format': 'PDF'}),
    ('PrintDisplay', 'DSS_TREND', {'Format': 'VECTOR'}),
    ('PrintDisplay', 'DSS_TELEMETRY', {'Printer': 'unknown'}),
    ('CloseDisplay', 'DSS_TELEMETRY', {'Monitor': 1}),
    ('PrintDisplay', 'DSS_TELEMETRY', {}),
    ('CloseDisplay', 'DSS_TELEMETRY', {}),
])
def test_invalid_request_has_no_intent_or_effect_and_valid_recovery(bridge, method, name, options):
    before = bridge.ground.state()
    with pytest.raises(grpc.RpcError) as rejected:
        bridge.call(method, name, **options)
    assert rejected.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.ground.state() == before
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0
    bridge.call('OpenDisplay')
    bridge.call('CloseDisplay')
    assert applications(bridge) == {}


def test_receipted_close_duplicate_returns_before_state_validation(bridge):
    bridge.call('OpenDisplay')
    bridge.request_id[0] = uuid.uuid4().hex
    bridge.call('CloseDisplay')
    bridge.call('CloseDisplay')
    assert applications(bridge) == {}
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 2
    bridge.who['controller_epoch'] = 0
    with pytest.raises(grpc.RpcError):
        bridge.call('CloseDisplay')


def test_monitoring_cannot_open_and_legacy_snapshot_survives_upgrade(bridge):
    snapshot = bridge.runtime.engine.telemetry()
    bridge.ground.update(lambda state: state['displays'].update(DSS_TELEMETRY=snapshot))
    bridge.who['mode'] = 'Monitoring'
    with pytest.raises(grpc.RpcError) as rejected:
        bridge.call('OpenDisplay')
    assert rejected.value.code() == grpc.StatusCode.PERMISSION_DENIED
    bridge.who['mode'] = 'Development'
    bridge.call('PrintDisplay', Format='VECTOR')
    app, = applications(bridge).values()
    assert snapshot_for(app['displays']['DSS_TELEMETRY'], bridge.ground.state()) == snapshot
    reopened = bridge.journal_type(bridge.path)
    try:
        ground = bridge.ground_type(bridge.transport, reopened)
        assert ground.state() == bridge.ground.state()
    finally:
        reopened.close()
    bridge.call('CloseDisplay')


def test_capacity_keeps_receipts_and_reuse_selects_latest_numeric_id(bridge):
    for _ in range(MAX_INSTANCES):
        bridge.call('OpenDisplay', Reuse=False)
    bridge.call('OpenDisplay', 'DSS_TREND', Reuse=True, Time=86400)
    assert 'DSS_TREND' in applications(bridge)[str(MAX_INSTANCES)]['displays']
    before = bridge.ground.state()
    with pytest.raises(grpc.RpcError) as rejected:
        bridge.call('OpenDisplay', Reuse=False)
    assert rejected.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.ground.state() == before
    bridge.call('CloseDisplay')
    assert len(applications(bridge)) == 1


def test_read_only_viewer_serves_instances_and_exact_print_downloads(bridge):
    from urllib.request import urlopen
    from urllib.error import HTTPError
    from openbexi_spell_dss.display_viewer import create_server, journal_state
    bridge.call('OpenDisplay', 'Workspaces/Operación', _OpenBEXIWorkspace=True, Monitor=2)
    bridge.call('PrintDisplay', 'Displays/Telemetría', Format='VECTOR')
    bridge.call('PrintDisplay', 'Displays/Telemetría', Format='PS', Printer='DSS_REPORTS')
    before = bridge.ground.state()
    read = lambda: journal_state(bridge.path, bridge.ground.namespace)
    server = create_server(read)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    try:
        with urlopen(base) as response:
            page = response.read().decode('utf-8')
        assert 'Displays/Telemetría' in page and 'monitor 2' in page
        assert '<svg ' in page and '/jobs/1' in page and '/jobs/2' in page
        for identity, job in before['display_jobs'].items():
            with urlopen(base + '/jobs/' + identity) as response:
                assert response.read() == job['content'].encode('ascii')
                assert response.headers['Content-Type'] == job['media_type']
        for invalid in ('/jobs/../1', '/jobs/01', '/missing'):
            with pytest.raises(HTTPError) as rejected:
                urlopen(base + invalid)
            assert rejected.value.code == 404
        assert read() == before
        assert bridge.ground.state() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


def test_known_full_spool_rejects_without_pending_intent(bridge):
    bridge.call('OpenDisplay')
    # Capacity is a persisted precondition; filling it does not exercise printing.
    bridge.ground.update(lambda state: state.update(display_jobs={str(i): {} for i in range(MAX_JOBS)}))
    before = bridge.ground.state()
    with pytest.raises(grpc.RpcError) as rejected:
        bridge.call('PrintDisplay')
    assert rejected.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.ground.state() == before
    assert bridge.journal.db.execute("SELECT count(*) FROM effects WHERE state='PENDING'").fetchone()[0] == 0
    bridge.call('CloseDisplay')


def test_all64_real_print_documents_fit_declared_spool_capacity(bridge):
    bridge.call('OpenDisplay')
    for _ in range(MAX_JOBS):
        bridge.call('PrintDisplay', Format='VECTOR')
    state = bridge.ground.state()
    assert len(state['display_jobs']) == MAX_JOBS
    assert len(json.dumps(state).encode()) < 1024 * 1024
    with pytest.raises(grpc.RpcError) as rejected:
        bridge.call('PrintDisplay', Format='VECTOR')
    assert rejected.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.ground.state() == state
    bridge.call('CloseDisplay')


def test_optional_validation_preserves_uncertain_and_cached_receipt_rules(tmp_path):
    patched = module('journal')
    journal = patched.Journal(tmp_path / 'effects.sqlite')
    who = dict(session=uuid.uuid4().hex, procedure=uuid.uuid4().hex, definition='test', version='test',
               controller_epoch=1, procedure_fence=1, mode='Development', release=None)
    request = uuid.uuid4().hex
    validations = []
    def invalid():
        validations.append(False)
        raise ValueError('Not open')
    try:
        with pytest.raises(ValueError, match='Not open'):
            journal.begin(who, request, 'close', b'request', validate=invalid)
        assert journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0
        assert journal.db.execute('SELECT count(*) FROM fences').fetchone()[0] == 0
        assert journal.begin(who, request, 'close', b'request', validate=lambda: validations.append(True)) is None
        for identity in (request, uuid.uuid4().hex):
            with pytest.raises(patched.UncertainEffect):
                journal.begin(who, identity, 'close', b'request', validate=invalid)
        assert validations == [False, True]
        journal.finish(who, request, b'')
        assert journal.begin(who, request, 'close', b'request', validate=invalid) == b''
        assert validations == [False, True]
        journal.begin(dict(who, controller_epoch=2), uuid.uuid4().hex, 'another', b'')
        with pytest.raises(PermissionError, match='Stale'):
            journal.begin(who, request, 'close', b'request', validate=invalid)
        assert validations == [False, True]
    finally:
        journal.close()


@pytest.mark.parametrize('bound', ['state-size', 'report-count'])
def test_shared_ground_capacity_rejects_before_intent_and_recovers(bridge, bound):
    if bound == 'state-size':
        bridge.ground.update(lambda state: state['resources'].update(padding='x' * 1030000))
        operation = 'OpenDisplay'
    else:
        bridge.call('OpenDisplay')
        bridge.ground.update(lambda state: state['reports'].update({str(i): {} for i in range(128)}))
        operation = 'PrintDisplay'
    before = bridge.ground.state()
    count = bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0]
    with pytest.raises(grpc.RpcError) as rejected:
        bridge.call(operation)
    assert rejected.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert bridge.ground.state() == before
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == count
    if bound == 'state-size':
        bridge.ground.update(lambda state: state['resources'].pop('padding'))
        bridge.call('OpenDisplay')
    else:
        bridge.ground.update(lambda state: state['reports'].clear())
        bridge.call('PrintDisplay')
    bridge.call('CloseDisplay')


def test_display_completion_delay_finishes_after_real_state_change(bridge):
    began = time.monotonic()
    bridge.call('OpenDisplay', Delay=.05)
    assert time.monotonic()-began >= .05
    assert len(applications(bridge)) == 1
    bridge.call('PrintDisplay', Delay=0, Format='ps')
    assert bridge.ground.state()['display_jobs']['1']['format'] == 'PS'
    bridge.call('CloseDisplay', Delay=0)


@pytest.mark.parametrize('delay', [-1, True, 31, float('nan'), None])
def test_invalid_display_delay_rejects_before_an_effect_and_recovers(bridge, delay):
    before = bridge.ground.state()
    with pytest.raises((grpc.RpcError, ValueError)):
        bridge.call('OpenDisplay', Delay=delay)
    assert bridge.ground.state() == before
    assert bridge.journal.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0
    bridge.call('OpenDisplay', Delay=0)
    bridge.call('CloseDisplay', Delay=0)


@pytest.mark.parametrize('name', list(display_patches.PREIMAGES))
def test_source_recipe_rejects_drift_and_keeps_compilable_sources(name):
    raw = original(name)
    assert hashlib.sha256(raw).hexdigest() == display_patches.PREIMAGES[name]
    compile(display_patches.apply(name, raw), name, 'exec')
    with pytest.raises(ValueError, match='preimage'):
        display_patches.apply(name, raw + b'\n')
