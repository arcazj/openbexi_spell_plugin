"""Strict native command diagnostics and narrow language requirement candidates."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from evidence_database import evidence_database
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'conformance'), str(ROOT/'distribution'), str(ROOT/'driver_plugin/src')]
from dss.packets import decode_tc
from evidence_sources import source_bytes
from installed_provenance import verify_capture
from run_language_regressions import validate_report
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
import command_group_review

DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
DEPENDENCIES = {
    'EXAMPLE-061': ('Time',), 'SECTION-4-5-2-048': ('Time',),
    'EXAMPLE-062': ('ReleaseTime',), 'MODIFIER-RELEASETIME': ('ReleaseTime',), 'SECTION-4-5-3-049': ('ReleaseTime',),
    'EXAMPLE-063': ('LoadOnly',), 'MODIFIER-LOADONLY': ('LoadOnly',), 'SECTION-4-5-4-050': ('LoadOnly',),
    'EXAMPLE-072': ('Timeout',), 'SECTION-4-5-11-057': ('Timeout',),
    'EXAMPLE-073': ('addInfo',), 'KEYWORD-ARGUMENT-ADDINFO': ('addInfo',), 'SECTION-4-5-12-058': ('addInfo',),
    'EXAMPLE-074': ('SendDelay',), 'MODIFIER-SENDDELAY': ('SendDelay',), 'SECTION-4-5-13-059': ('SendDelay',),
    'EXAMPLE-065': ('ConfirmCritical',), 'MODIFIER-CONFIRMCRITICAL': ('ConfirmCritical',), 'SECTION-4-5-6-052': ('ConfirmCritical',),
    'EXAMPLE-067': ('Sequence',), 'KEYWORD-ARGUMENT-SEQUENCE': ('Sequence',), 'SECTION-4-5-8-054': ('Sequence',),
    'EXAMPLE-070': ('Group',), 'MODIFIER-GROUP': ('Group',),
    'EXAMPLE-071': ('Block',), 'SECTION-4-5-10-056': ('Group', 'Block'),
}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()), sha256=sha(path))
digest = lambda value: hashlib.sha256(value).hexdigest()


def frozen(name, revision):
    module = types.ModuleType('_command_report_'+Path(name).stem)
    exec(compile(source_bytes(ROOT, name, revision), name, 'exec'), module.__dict__)
    return module


def verify_overlay(raw, overlay, revision, recipe_name, provenance_name, previous):
    runtime = raw['runtime_sources']
    record = runtime['overlay']
    assert sha(overlay/'base.json') == runtime['base_sha256']
    base = read(overlay/'base.json')
    assert base == previous and base['integrated'] == runtime['integrated']
    assert record['files'] == {p.relative_to(overlay).as_posix(): sha(p)
        for p in overlay.rglob('*') if p.is_file() and p.name != 'base.json'}
    recipe = frozen('source_port/'+recipe_name, revision)
    assert record['files'][recipe_name] == raw['inputs']['source_port/'+recipe_name]
    assert record['files'][provenance_name] == raw['inputs']['conformance/'+provenance_name]
    assert read(overlay/'manifest.json') == record['manifest']
    assert set(record['manifest']) == set(recipe.PREIMAGES)
    expected = dict(base['installed'])
    for name, row in record['manifest'].items():
        before, after = overlay/'original'/name, overlay/'patched'/name
        assert expected[name] == sha(before) == row['preimage_sha256']
        assert recipe.apply(name, before.read_bytes()) == after.read_bytes()
        expected[name] = sha(after)
        assert row['sha256'] == expected[name]
    assert set(record['added_sources']) == set(frozen('conformance/'+provenance_name, revision).ADDED)
    for name, value in record['added_sources'].items():
        assert name not in expected
        assert value == sha(overlay/'modules'/name) == raw['inputs']['driver_plugin/src/'+name]
        expected[name] = value
    assert runtime['installed'] == expected


def verify_cases(path, image, revision, kind):
    raw = read(path)
    cases = frozen('conformance/command_'+kind+'_cases.py', revision).CASES
    validate_report(path, image, len(cases), source_revision=revision)
    assert set(raw['checks']) == set(cases)
    assert raw['passed'] and not raw['timed_out'] and raw['controller_exit_code'] == 0
    assert raw['diagnostic_only'] and not raw['qualified_contracts']
    workspace = path.parent/'workspace'
    assert read(workspace/'checks.json') == raw['checks']
    assert read(workspace/'runtime.json') == raw['runtime_sources']
    assert read(workspace/'host-inputs.json') == raw['host_inputs']
    verify_capture(raw['runtime_sources']['integrated'], raw['inputs'])
    assert raw['host_inputs'] == {Path(n).name: v for n, v in raw['inputs'].items()
                                 if n.startswith('host_runtime/python/') and n.endswith('.py')}
    for name, value in raw['inputs'].items():
        assert sha(path.parent/'inputs'/name) == value
        if name.startswith('src/dss/'):
            assert sha(workspace/'fixture'/name.removeprefix('src/')) == value
    for name in ('command_'+kind+'_cases.py', 'command_'+kind+'_controller.py', 'installed_provenance.py'):
        assert sha(workspace/name) == raw['inputs']['conformance/'+name]
    evidence = {}
    for name, spec in cases.items():
        row = raw['checks'][name]
        project = workspace/name.replace(':', '-')
        assert row['passed'] and row['dimension'] == spec['dimension'] and row['status'] == 'FINISHED'
        assert row['source'] == spec['source'] == (project/'main.py').read_text(encoding='utf-8')
        assert row['observed'] == read(project/'observed.json')
        assert row['result'] == read(project/'result.json') == {'completed': True}
        calls = row['observed']['calls']
        assert calls and all(c['returned'] is True and c['return_type'] == 'bool' for c in calls if 'returned' in c)
        assert sum('error_type' in c for c in calls) == (spec['dimension'] in ('failure', 'recovery'))
        assert sha(project/'native.log') == row['native_log_sha256']
        log = (project/'native.log').read_text(encoding='utf-8')
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        assert sha(project/'events.json') == row['events_sha256']
        events = read(project/'events.json')
        assert not any(e.get('event') == 'connectionError' for e in events)
        native = [e['message']['fields'] for e in events
                  if e.get('message', {}).get('fields', {}).get('ItemType') == 'EXECUTION']
        prompts = [e['message']['fields'] for e in events if e.get('message', {}).get('id') == 'MSG_PROMPT']
        if kind == 'scheduling':
            assert prompts == []
        else:
            assert prompts == [r['fields'] for r in row['prompts']]
            assert [r['answer'] for r in row['prompts']] == spec['prompt_answers']
            for prompt in row['prompts']:
                assert prompt['fields']['ExpectedValues'].split('\x04') == ['O', 'C']
                assert 'Confirm critical command execution:' in prompt['fields']['Text']
                assert prompt['before_operations'] == [] and prompt['before_dss']['core']['commands_executed'] == 0
        receipts = row['receipts']
        assert len(receipts) == spec['expected_stages']
        assert row['initial_dss']['core']['commands_executed'] == 0
        assert row['final_dss']['core']['commands_executed'] == spec['expected_executions']
        with evidence_database(project/'dss.sqlite') as db:
            actual = db.execute('SELECT request_hash,raw_tc,acknowledgement FROM operations ORDER BY rowid').fetchall()
        assert len(actual) == len(receipts)
        frames = []
        for (request_hash, packet, ack), receipt in zip(actual, receipts):
            assert request_hash == receipt['request_hash']
            assert packet.hex() == receipt['packet_hex'] and digest(packet) == receipt['packet_sha256']
            assert json.loads(ack) == receipt['acknowledgement']
            frame = decode_tc(packet)
            assert frame['stage'] == receipt['acknowledgement']['stage']
            frames.append(frame)
        transports = [f for f in frames if f['stage'] == 'TRANSPORT']
        load_only = ('LoadOnly' in name and spec['expected_executions'] == 0 and bool(frames))
        stage_order = ['TRANSPORT', 'LOADING'] if load_only else ['TRANSPORT', 'LOADING', 'RELEASE', 'ACKNOWLEDGEMENT', 'ONBOARD_EXECUTION']
        assert [f['stage'] for f in frames] == stage_order*len(transports)
        expected_members = spec.get('expected_members', ['CMD1'] if frames else [])
        assert [f['command_name'] for f in transports] == expected_members
        successful = [r for r in row['rpc'] if r['path'].endswith('_TC/SendCommand') and 'response' in r]
        assert len(successful) == len(transports)
        for wire, transport in zip(successful, transports):
            command = p.CommandDesc.FromString(bytes.fromhex(wire['request']))
            assert command.command.mnemonic == transport['command_name']
            options = unpack(command.config)
            assert transport.get('additional_info') == options.get('addInfo')
            if 'Time' in options:
                assert transport['execution_time_unix_ns'] == round(options['Time']*1000000000)
            first_ack = next(r['acknowledgement'] for r in receipts
                             if r['acknowledgement']['operation_id'] == transport['operation_id'])
            utc = first_ack['clock_epoch_unix_ns']+first_ack['simulation_time_ns']
            if 'ReleaseTime' in options:
                assert utc >= round(options['ReleaseTime']*1000000000)
            if 'SendDelay' in options:
                assert first_ack['simulation_time_ns'] >= round(options['SendDelay']*1000000000)
            if name.startswith('Timeout:'):
                assert options['Timeout'] == (31 if name.endswith(':boundary') else 60)
        if frames:
            finals = {n['ItemName']: n for n in native}
            assert finals
            for item in finals.values():
                assert set(item['ItemStatus'].split(',,')) == {'SUCCESS'}
                assert set(item['ItemValue'].split(',,')) == {'LOADING' if load_only else 'ONBOARD_EXECUTION'}
            if name.startswith('Sequence'):
                sequence = next(n for n in finals.values() if n['ItemName'].startswith('SEQ'))
                expected = sequence['ItemName'].split(',,')[0:1]+[str(i)+'@'+n for i,n in enumerate(expected_members)]
                assert sequence['ItemName'].split(',,') == expected
        if spec['dimension'] == 'encoding' and name.split(':')[0] in ('addInfo', 'LoadOnly', 'Sequence', 'ConfirmCritical'):
            expected = {'note': 'caf\u00e9 \u03bb'}
            if kind == 'catalog':expected['note'] += ' \u9065\u6e2c'
            elif name.startswith('addInfo:'):expected['nested'] = {'value': '\u9065\u6e2c'}
            assert all(frame['additional_info'] == expected for frame in frames)
        if spec['dimension'] in ('positive', 'recovery', 'encoding'):
            observations = row['clock_observations']
            if name.startswith('Time:'):
                assert any(r['stages'] == stage_order[:4] and r['before']['core']['commands_executed'] == 0 for r in observations)
                target = transports[0]['execution_time_unix_ns']
                executed = receipts[-1]['acknowledgement']
                assert executed['clock_epoch_unix_ns']+executed['simulation_time_ns'] >= target
            if name.startswith(('ReleaseTime:', 'SendDelay:')):
                assert any(r['stages'] == [] for r in observations)
        evidence[name] = dict(deepcopy(row), contracts=[],
            oracle='Native helper return and notifications, original binary RPC, independently decoded TCP packets, immutable SQLite receipts and clock observations')
    return raw, evidence


def qualify(manifest):
    baseline = manifest['baseline']
    path = Path(baseline['path'])
    assert sha(path) == baseline['sha256']
    raw_base = read(path)
    assert not raw_base['passed'] and not raw_base['timed_out'] and len(raw_base['checks']) == 8
    assert read(path.parent/'workspace/checks.json') == raw_base['checks']
    for name, value in raw_base['inputs'].items():
        assert digest(source_bytes(ROOT, name, baseline['source_revision'])) == value
    for name, row in raw_base['checks'].items():
        assert not row['passed'] and row['observed'] == read(path.parent/'workspace'/name/'observed.json')
        if name != 'api-surface':
            assert all(c['error_type'] == 'DriverException' for c in row['observed']['calls'])
    assert raw_base['checks']['api-surface']['observed']['modifiers']['Group'] is None
    display = read(Path(manifest['display']['path']))
    assert sha(Path(manifest['display']['path'])) == manifest['display']['sha256'] and display['passed']
    previous = display['runtime_sources']
    checks, artifacts, raws = {}, {}, {}
    for kind, recipe, provenance in (
            ('scheduling', 'command_feature_patches.py', 'command_provenance.py'),
            ('catalog', 'command_catalog_patches.py', 'command_catalog_provenance.py'),
            ('group', 'command_group_patches.py', 'command_group_provenance.py')):
        item = manifest[kind]
        path = Path(item['path'])
        assert sha(path) == item['sha256']
        if kind == 'group':
            review = command_group_review.review(path, Path(item['overlay']), item['source_revision'], item['image'])
            raw = read(path)
            leaves = {k: dict(deepcopy(v), contracts=[], oracle='Independent Group/Block receipt, native status, partial failure and competing TCP source review')
                      for k,v in raw['checks'].items()}
        else:
            raw, leaves = verify_cases(path, item['image'], item['source_revision'], kind)
        verify_overlay(raw, Path(item['overlay']), item['source_revision'], recipe, provenance, previous)
        assert not set(checks) & set(leaves)
        checks.update(leaves)
        previous = raw['runtime_sources']
        raws[kind] = ref(path)
        artifacts[kind] = {p.relative_to(path.parent/'workspace').as_posix(): sha(p)
                          for p in (path.parent/'workspace').rglob('*') if p.is_file()}
    inventory = {r['id'] for r in read(ROOT/'conformance/inventory.json')['rows']}
    candidates = []
    for short, families in DEPENDENCIES.items():
        contract = 'CMP-LRM244-'+short
        assert contract in inventory
        candidates.append(contract)
        for dimension in DIMENSIONS:
            dependencies = [f+':'+dimension for f in families]
            encoding = [f+':encoding' for f in families]
            assert all(checks[k]['passed'] for k in dependencies+encoding)
            checks[contract+':'+dimension] = dict(passed=True, contracts=[contract], dimension=dimension,
                dependencies=dependencies, encoding_checks=encoding,
                oracle='All named native behavior and encoding cases are mandatory; no rejected unsupported feature is treated as support')
    return dict(passed=True, runtime_image=manifest['group']['image'], raw=raws,
        inputs={n: sha(ROOT/n) for n in ('conformance/command_features_report.py', 'conformance/command_group_review.py',
                                       'conformance/inventory.json', 'docs/reference/SPELL - Language Reference - 2.4.4.pdf')},
        manifest=manifest, artifacts=artifacts, checks=checks, candidate_contracts=candidates, qualified_contracts=[],
        exclusions=['Function-wide Send/BuildTC and TC item aggregates', 'Broad Time/Timeout/Block modifiers',
                    'Combined telemetry verification and automatic limit adjustment'],
        scope='Retained diagnostic images; fresh package composition and complete language regressions remain required',
        full_v05_accepted=False, full_v06_accepted=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'conformance/evidence/command_features.json')
    args = parser.parse_args()
    result = qualify(read(args.manifest))
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(passed=True, candidates=len(result['candidate_contracts']), output=str(args.output))))
