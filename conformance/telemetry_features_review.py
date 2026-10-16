"""Independent telemetry evidence review over the original RPC and DSS packets."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'distribution'), str(ROOT/'driver_plugin/src')]
from evidence_sources import source_bytes
from run_language_regressions import validate_report
from limit_features_review import overlay_proof as limit_overlay
from dss.packets import decode_tm
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()), sha256=sha(path))
BOUNDARY_ERRORS = {'quality':2, 'validity':1, 'freshness':1, 'availability':1, 'link':1,
                   'minute':1, 'printed':0, 'between-list':0}


def frozen(name, revision):
    module = types.ModuleType('_telemetry_review_'+Path(name).stem)
    source = source_bytes(ROOT, name, revision)
    if name.endswith('/telemetry_features_cases.py'):
        anchor = b'from telemetry_surface_cases import HEADER'
        assert source.count(anchor) == 1
        source = source.replace(anchor, b'')
        module.HEADER = frozen('conformance/telemetry_surface_cases.py', revision).HEADER
    exec(compile(source, name, 'exec'), module.__dict__)
    return module


def provenance(raw, directory, limit_directory, revision):
    runtime = raw['runtime_sources']
    assert runtime['profile'] == 'fresh-composed-limit-telemetry-overlays/1'
    base = read(directory/'base.json')
    assert sha(directory/'base.json') == runtime['base_sha256']
    assert runtime['integrated'] == base['integrated']
    limit_overlay(dict(runtime_sources=base, inputs=raw['inputs']), limit_directory, revision)
    record = runtime['overlay']
    assert record['files'] == {q.relative_to(directory).as_posix(): sha(q) for q in directory.rglob('*')
                              if q.is_file() and q.name != 'base.json' and '__pycache__' not in q.parts}
    recipe = frozen('source_port/telemetry_feature_patches.py', revision)
    assert sha(directory/'telemetry_feature_patches.py') == raw['inputs']['source_port/telemetry_feature_patches.py']
    assert read(directory/'manifest.json') == record['manifest']
    assert set(record['manifest']) == set(recipe.PREIMAGES)
    expected = dict(base['installed'])
    for name, row in record['manifest'].items():
        before, after = directory/'original'/name, directory/'patched'/name
        assert sha(before) == expected[name] == row['preimage_sha256']
        assert recipe.apply(name, before.read_bytes()) == after.read_bytes()
        expected[name] = sha(after)
        assert row['sha256'] == expected[name]
    additions = frozen('conformance/telemetry_features_provenance.py', revision).ADDED
    assert set(record['added_sources']) == set(additions)
    for name in additions:
        assert name not in expected
        expected[name] = sha(directory/'modules'/name)
        assert expected[name] == record['added_sources'][name] == raw['inputs']['driver_plugin/src/'+name]
    assert runtime['installed'] == expected


def case_proof(name, spec, row, project):
    assert row['passed'] and row['status'] == 'FINISHED'
    assert not any(key.endswith('_error') for key in row)
    assert row['source'] == spec['source'] == (project/'main.py').read_text(encoding='utf-8')
    assert row['dimension'] == spec['dimension'] and row['feature'] == spec['feature']
    assert read(project/'result.json') == row['result'] == {'completed':True}
    observed = read(project/'observed.json')
    assert observed == row['observed'] and observed['calls']
    assert all(value['actual'] == value['expected'] for value in observed['observations'] if 'actual' in value)
    feature, dimension = name.split(':')
    expected_errors = (0 if dimension == 'positive' else BOUNDARY_ERRORS[feature] if dimension == 'boundary'
                       else (4 if feature == 'minute' else 0 if feature == 'printed' else 1) if dimension == 'failure' else 1)
    failures = [call for call in observed['calls'] if 'error_type' in call]
    assert len(failures) == expected_errors and all(call['error_type'] == 'DriverException' for call in failures), name
    assert sha(project/'native.log') == row['native_log_sha256']
    log = (project/'native.log').read_text(encoding='utf-8')
    assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
    assert sha(project/'events.json') == row['events_sha256']
    events = read(project/'events.json')
    assert not any(event.get('event') == 'connectionError' or event.get('message', {}).get('id') in ('MSG_ERROR','MSG_PROMPT') for event in events)
    assert row['receipts'] == []
    with sqlite3.connect((project/'dss.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        scenarios = {key:dict(epoch=epoch, state=json.loads(state), faults=json.loads(faults))
                     for key, epoch, state, faults in db.execute('SELECT id,epoch,state,faults FROM scenarios')}
        packets = [packet for packet, in db.execute('SELECT packet FROM packets')]
        assert db.execute('SELECT count(*) FROM operations').fetchone()[0] == 0
    assert scenarios[row['final_dss']['scenario_id']]['state'] == row['final_dss']
    initial = scenarios[row['initial_dss']['scenario_id']]
    assert all(initial['faults'][key] == value for key, value in spec.get('faults', {}).items())
    decoded = [decode_tm(packet) for packet in packets]
    samples = [item for item in decoded if 'items' in item]
    assert samples
    controls = row['fixture_controls']
    assert [entry['request'] for entry in observed['fixtures']] == [entry['command'] for entry in controls]
    for entry, saved in zip(controls, observed['fixtures']):
        command = entry['command']
        response = read(project/('fixture-'+command['token']+'.json'))
        assert response == saved['response']
        assert response['state'] == entry['after'] and response['packet_hex'] == entry['after_packet_hex']
        for label in ('before','after'):
            packet = bytes.fromhex(entry[label+'_packet_hex'])
            assert packet in packets
            message = decode_tm(packet)
            assert message['scenario_id'] == entry[label]['scenario_id']
            assert message['satellite_epoch'] == entry[label]['epoch']
        if command['action'] == 'reset':
            assert entry['before']['epoch'] != entry['after']['epoch']
            scenario = scenarios[entry['after']['scenario_id']]
            assert all(scenario['faults'][key] == value for key, value in command['faults'].items())
    with sqlite3.connect((project/'driver.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        grounds = [json.loads(state) for state, in db.execute('SELECT state FROM ground')]
        journal = db.execute('SELECT digest,state,receipt FROM effects').fetchall()
    assert row['final_ground'] in grounds
    assert all(not value['limits'] and not value['injections'] for value in grounds)
    responses = Counter()
    refreshes, links = [], []
    for call in row['rpc']:
        service_name, method_name = call['path'].split('/')[1:]
        assert not service_name.endswith('_TC')
        method = p.DESCRIPTOR.services_by_name[service_name.removeprefix('spell.driver.')].methods_by_name[method_name]
        request_bytes = bytes.fromhex(call['request'])
        request = GetMessageClass(method.input_type).FromString(request_bytes)
        if 'response' not in call:
            assert 'error' in call
            continue
        response_bytes = bytes.fromhex(call['response'])
        answer = GetMessageClass(method.output_type).FromString(response_bytes)
        responses[(hashlib.sha256(call['path'].encode()+b'\0'+request_bytes).hexdigest(), response_bytes)] += 1
        if method_name == 'SetLink':
            assert request.name == 'TM' and answer.value is True
            links.append(request.status)
        if method_name == 'RefreshItem':
            matched = [(packet,item) for packet in samples for item in packet['items']
                       if item['item_id'] == request.item.mnemonic
                       and item['engineering']['value'] == unpack(answer.engValue)
                       and item['raw']['value'] == unpack(answer.rawValue)
                       and datetime.fromtimestamp(packet['acquired_at_unix_ns']/1e9, timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f') == answer.timestamp]
            assert matched
            if answer.validity:
                assert any(item['validity'] == 'VALID' and item['quality'] == 'GOOD' and packet['synchronization_state'] == 'COMPLETE' for packet,item in matched)
            refreshes.append(dict(name=request.item.mnemonic, settings=unpack(request.config), valid=answer.validity,
                                  seconds=call['elapsed'], started=call['started']))
    assert links == [entry['command']['enabled'] for entry in controls if entry['command']['action'] == 'link']
    for digest,state,receipt in journal:
        assert state == 'RECEIPTED' and responses[(digest, receipt)] > 0
    if name == 'quality:boundary':
        assert [entry['command']['faults']['telemetry_quality'] for entry in controls] == ['SUSPECT','UNKNOWN']
        assert len({entry['after']['scenario_id'] for entry in controls}) == 2
        assert [entry['valid'] for entry in refreshes] == [False,False]
    if name == 'freshness:boundary':
        assert [entry['valid'] for entry in refreshes] == [True,False]
        assert refreshes[1]['started']-refreshes[0]['started'] >= 2.5
    if name == 'minute:positive':
        acquisition, = refreshes
        assert acquisition['settings']['Wait'] is True and acquisition['settings']['Timeout'] == 60
        assert 35 <= acquisition['seconds'] < 45
        assert controls[0]['command'] == dict(action='feed', enabled=True, delay=36, token=controls[0]['command']['token'])
        elapsed, = [item['acquisition_elapsed'] for item in observed['observations'] if 'acquisition_elapsed' in item]
        assert 35 <= elapsed < 45
    if feature == 'printed':
        expected_values = {'positive':[True,True], 'boundary':[True,False], 'failure':[False,False], 'recovery':[True,True]}[dimension]
        names = ['TM.POWER.BUS_VOLTAGE', 'TM.POWER.BUS_VOLTAGE' if dimension == 'boundary' else 'TM.THERMAL.MODE']
        expected_lines = [str(index)+': '+parameter+' : '+str(value) for index,(parameter,value) in enumerate(zip(names,expected_values))]
        printed = [item['displayed'] for item in observed['observations'] if 'displayed' in item]
        assert printed == expected_lines
        actual = [event['message']['fields']['Text'] for event in events if event.get('message',{}).get('id') == 'MSG_WRITE'
                  and event['message']['fields'].get('MsgType') == 'DISPLAY'
                  and event['message']['fields'].get('Scope') == '1']
        assert actual == expected_lines
    if name == 'between-list:boundary':
        assert [item['actual'] for item in observed['observations']] == [True,True,False,False]
    return dict(passed=True, dimension=dimension, contracts=[], api_failures=expected_errors,
        packet_count=len(samples), scenario_count=len(scenarios), refreshes=refreshes,
        observations=observed['observations'], oracle='Original native calls and emitted messages agree with immutable DSS packets, epochs and original protobuf responses')


def review(path, directory, limit_directory, revision, image):
    raw = read(path)
    cases = frozen('conformance/telemetry_features_cases.py', revision).CASES
    validate_report(path, image, 32, source_revision=revision)
    assert raw['passed'] and not raw['timed_out'] and raw['controller_exit_code'] == 0
    assert raw['diagnostic_only'] and raw['qualified_contracts'] == []
    assert len(cases) == 32 and set(raw['checks']) == set(cases)
    workspace = path.parent/'workspace'
    assert read(workspace/'checks.json') == raw['checks'] and read(workspace/'runtime.json') == raw['runtime_sources']
    assert raw['artifacts'] == {q.relative_to(workspace).as_posix(): sha(q) for q in workspace.rglob('*') if q.is_file()}
    for name,digest in raw['inputs'].items():
        assert sha(path.parent/'inputs'/name) == digest
        if name.startswith('src/dss/'):assert sha(workspace/'fixture'/name.removeprefix('src/')) == digest
    for name in ('telemetry_surface_cases.py','telemetry_features_cases.py','telemetry_features_controller.py','telemetry_features_provenance.py','installed_provenance.py'):
        assert sha(workspace/name) == raw['inputs']['conformance/'+name]
    assert read(workspace/'host-inputs.json') == raw['host_inputs']
    provenance(raw, directory, limit_directory, revision)
    checks = {name:case_proof(name,cases[name],row,workspace/name.replace(':','__')) for name,row in raw['checks'].items()}
    return dict(passed=True, runtime_image=image, source_revision=revision, raw=ref(path), checks=checks,
        overlay=str(directory.resolve()), limit_overlay=str(limit_directory.resolve()),
        inputs={name:sha(ROOT/name) for name in ('conformance/telemetry_features_review.py','conformance/limit_features_review.py',
                                               'tests/test_telemetry_features_review.py')},
        source_inputs=raw['inputs'], artifacts=raw['artifacts'], qualified_contracts=[], full_v05_accepted=False,
        scope='Independent telemetry diagnostic review; composed regressions and requirement mapping remain pending')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('raw','overlay','limit-overlay','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('revision','image'):parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    result = review(args.raw,args.overlay,args.limit_overlay,args.revision,args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,cases=len(result['checks']),output=str(args.output))))
