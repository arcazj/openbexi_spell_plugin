"""Replay native limit evidence against frozen sources, RPC and SQLite receipts.

This produces diagnostic evidence only. The composed runtime regression and
requirement-by-requirement mapping remain mandatory before promotion.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
from evidence_database import evidence_database
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'distribution'), str(ROOT/'driver_plugin/src')]
from evidence_sources import source_bytes
from installed_provenance import verify_capture
from run_language_regressions import validate_report
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()), sha256=sha(path))

# Literal expected alarm transitions; no production classifier is invoked.
ALARMS = {
    'activation:positive': [False], 'activation:recovery': [True],
    'status:positive': [False, True, True, False], 'status:boundary': [False, True],
    'status:recovery': [True, False],
    'step:positive': [False, False, True, False, True],
    'spike:positive': [False, False, True, False, True],
    'step:boundary': [False, False, True], 'spike:boundary': [False, False, True],
    'step:recovery': [False, True, False], 'spike:recovery': [False, True, False],
    'hysteresis:positive': [False, False, True],
    'hysteresis:boundary': [True, True, False, False],
    'hysteresis:failure': [False, False, True],
    'hysteresis:recovery': [False, True, False, False, True],
    'alarm-control:positive': [True, False, True], 'alarm-control:boundary': [False, False],
    'alarm-control:recovery': [False, True, False, True],
    'adjust-analog:boundary': [False, True], 'adjust-analog:recovery': [False],
    'adjust-status:positive': [False], 'adjust-status:recovery': [True, False],
    'limit-file:recovery': [False], 'paired-properties:boundary': [False],
    'paired-properties:recovery': [False], 'round-trip:recovery': [False],
    'adjust-filter:recovery': [False],
}
MUTATORS = {'SetLimits', 'SetGroundParameter', 'EnableAlarm', 'DisableAlarm', 'AdjustLimits',
            'LoadLimits', 'RestoreNormalLimits'}
EFFECT_METHODS = {'SetLimits', 'InjectItem', 'RestoreNormalLimits'}


def frozen(name, revision):
    module = types.ModuleType('_limit_review_'+Path(name).stem)
    exec(compile(source_bytes(ROOT, name, revision), name, 'exec'), module.__dict__)
    return module


def overlay_proof(raw, directory, revision):
    runtime = raw['runtime_sources']
    assert runtime['profile'] == 'fresh-composed-wheel-plus-limit-overlay/1'
    assert sha(directory/'base.json') == runtime['base_sha256']
    base = read(directory/'base.json')
    assert base['profile'] == 'fresh-composed-display-command-wheel/1'
    assert base['integrated'] == runtime['integrated']
    verify_capture(runtime['integrated'], raw['inputs'])
    record = runtime['overlay']
    assert record['files'] == {q.relative_to(directory).as_posix(): sha(q) for q in directory.rglob('*')
                              if q.is_file() and q.name != 'base.json' and '__pycache__' not in q.parts}
    recipe = frozen('source_port/limit_feature_patches.py', revision)
    assert sha(directory/'limit_feature_patches.py') == raw['inputs']['source_port/limit_feature_patches.py']
    assert set(record['manifest']) == set(recipe.PREIMAGES)
    assert read(directory/'manifest.json') == record['manifest']
    expected = dict(base['installed'])
    for name, row in record['manifest'].items():
        before, after = directory/'original'/name, directory/'patched'/name
        assert sha(before) == expected[name] == row['preimage_sha256']
        assert recipe.apply(name, before.read_bytes()) == after.read_bytes()
        expected[name] = sha(after)
        assert row['sha256'] == expected[name]
    additions = frozen('conformance/limit_features_provenance.py', revision).ADDED
    assert set(record['added_sources']) == set(additions)
    for name in additions:
        assert name not in expected
        expected[name] = sha(directory/'modules'/name)
        assert expected[name] == record['added_sources'][name] == raw['inputs']['driver_plugin/src/'+name]
    assert runtime['installed'] == expected


def verify_case(name, spec, row, project, normal_digest):
    assert row['passed'] and row['status'] == 'FINISHED' and not row.get('sanitizer_error')
    assert row['source'] == spec['source'] == (project/'main.py').read_text(encoding='utf-8')
    assert row['feature'] == spec['feature'] and row['dimension'] == spec['dimension']
    assert read(project/'result.json') == row['result'] == {'completed': True}
    observed = read(project/'observed.json')
    assert observed == row['observed'] and observed['calls']
    assert all(value['actual'] == value['expected'] for value in observed['observations'])
    api_alarms = [call['returned'] for call in observed['calls'] if call['function'] == 'IsAlarmed' and 'returned' in call]
    assert api_alarms == ALARMS.get(name, []), (name, api_alarms)
    assert all(call['return_type'] == 'bool' and type(call['returned']) is bool
               for call in observed['calls'] if call['function'] == 'IsAlarmed' and 'returned' in call)
    assert sha(project/'native.log') == row['native_log_sha256']
    log = (project/'native.log').read_text(encoding='utf-8')
    assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
    assert sha(project/'events.json') == row['events_sha256']
    assert not any(event.get('event') == 'connectionError' or event.get('message', {}).get('id') in ('MSG_ERROR', 'MSG_PROMPT')
                   for event in read(project/'events.json'))
    assert row['receipts'] == []
    assert row['initial_dss']['core']['commands_executed'] == row['final_dss']['core']['commands_executed'] == 0
    with evidence_database(project/'driver.sqlite') as db:
        ground, = db.execute('SELECT state FROM ground').fetchall()
        assert json.loads(ground[0]) == row['final_ground']
        journal = db.execute('SELECT digest,state,receipt,authority FROM effects').fetchall()
    received = Counter()
    successes = Counter()
    rpc_alarms = []
    for call in row['rpc']:
        service_name, method_name = call['path'].split('/')[1:]
        service = p.DESCRIPTOR.services_by_name[service_name.removeprefix('spell.driver.')]
        method = service.methods_by_name[method_name]
        request = GetMessageClass(method.input_type).FromString(bytes.fromhex(call['request']))
        if 'response' not in call:
            assert 'error' in call
            continue
        response_bytes = bytes.fromhex(call['response'])
        answer = GetMessageClass(method.output_type).FromString(response_bytes)
        digest = hashlib.sha256(call['path'].encode()+b'\0'+bytes.fromhex(call['request'])).hexdigest()
        received[(digest, response_bytes)] += 1
        if method_name in EFFECT_METHODS:
            assert answer.value is True
            successes[(digest, response_bytes)] += 1
        if method_name == 'SetLimits':
            wire = unpack(request.set.limitset)
            assert wire['LimitProfile'] == 'OPENBEXI_LIMITS_1'
            assert wire['Operation'] in ('Modify', 'Alarm', 'Adjust', 'Load')
        if method_name == 'IsAlarmed':rpc_alarms.append(answer.value)
    assert rpc_alarms == api_alarms
    stored = Counter()
    for digest, state, receipt, authority in journal:
        assert state == 'RECEIPTED' and type(receipt) is bytes
        assert json.loads(authority)['definition'] == name
        assert received[(digest, receipt)] > 0
        stored[(digest, receipt)] += 1
    assert all(stored[key] == count for key, count in successes.items())
    successful_api_mutations = sum(call['function'] in MUTATORS and call.get('returned') is True for call in observed['calls'])
    assert sum(successes.values()) == successful_api_mutations
    for uri, digest in row['final_ground'].get('limit_files', {}).items():
        assert uri == 'limits://normal' and digest == normal_digest
    return dict(passed=True, dimension=spec['dimension'], contracts=[],
        source_sha256=sha(project/'main.py'), observations=observed['observations'],
        alarm_transitions=api_alarms, successful_mutations=successful_api_mutations,
        immutable_receipts=len(journal), final_ground=row['final_ground'],
        oracle='Literal native expectations, original protobuf responses and independently retained SQLite ground/effect records')


def review(path, directory, revision, image, selected):
    raw = read(path)
    cases = frozen('conformance/limit_features_cases.py', revision).CASES
    assert selected and set(selected) <= set(cases)
    validate_report(path, image, len(selected), source_revision=revision)
    assert raw['passed'] and not raw['timed_out'] and raw['controller_exit_code'] == 0
    assert raw['diagnostic_only'] and raw['qualified_contracts'] == []
    assert set(raw['checks']) == set(selected)
    workspace = path.parent/'workspace'
    assert read(workspace/'checks.json') == raw['checks']
    assert read(workspace/'runtime.json') == raw['runtime_sources']
    assert raw['artifacts'] == {q.relative_to(workspace).as_posix(): sha(q) for q in workspace.rglob('*') if q.is_file()}
    for name, digest in raw['inputs'].items():
        assert sha(path.parent/'inputs'/name) == digest
        if name.startswith('src/dss/'):assert sha(workspace/'fixture'/name.removeprefix('src/')) == digest
    for name in ('limit_features_cases.py', 'limit_features_controller.py', 'limit_features_provenance.py', 'installed_provenance.py'):
        assert sha(workspace/name) == raw['inputs']['conformance/'+name]
    assert read(workspace/'host-inputs.json') == raw['host_inputs']
    assert raw['host_inputs'] == {Path(name).name: value for name, value in raw['inputs'].items()
                                  if name.startswith('host_runtime/python/')}
    overlay_proof(raw, directory, revision)
    normal = raw['inputs']['driver_plugin/src/openbexi_spell_dss/limit_files/normal.json']
    checks = {name: verify_case(name, cases[name], row, workspace/name.replace(':', '__'), normal)
              for name, row in raw['checks'].items()}
    return dict(passed=True, runtime_image=image, source_revision=revision, raw=ref(path), overlay=str(directory.resolve()),
        checks=checks, source_inputs=raw['inputs'], artifacts=raw['artifacts'], qualified_contracts=[],
        full_v05_accepted=False, scope='Independent limit diagnostic review; composed runtime and requirement mapping pending')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--overlay', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--case', action='append')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selected = args.case or list(frozen('conformance/limit_features_cases.py', args.revision).CASES)
    result = review(args.raw, args.overlay, args.revision, args.image, selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, cases=len(result['checks']), output=str(args.output))))
