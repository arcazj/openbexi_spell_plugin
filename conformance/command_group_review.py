"""Independently replay native Group/Block evidence without promoting coverage."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'conformance'), str(ROOT/'distribution')]
from dss.packets import decode_tc
from evidence_sources import source_bytes
from installed_provenance import verify_capture
from run_language_regressions import validate_report

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_bytes())
ref = lambda p: dict(path=str(p.resolve()), sha256=sha(p))
canonical = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def frozen(name, revision):
    module = types.ModuleType('_group_review_' + Path(name).stem)
    source = source_bytes(ROOT, name, revision)
    if name == 'conformance/command_group_cases.py':
        dependency = b'from command_catalog_cases import HEADER'
        assert source.count(dependency) == 1
        source = source.replace(dependency, b'')
        module.HEADER = frozen('conformance/command_catalog_cases.py', revision).HEADER
    exec(compile(source, name, 'exec'), module.__dict__)
    return module


def review(path, overlay, revision, image, composed=False):
    raw = read(path)
    cases = frozen('conformance/command_group_cases.py', revision).CASES
    validate_report(path, image, len(cases), source_revision=revision)
    assert raw['passed'] and not raw['timed_out'] and raw['controller_exit_code'] == 0
    assert raw['diagnostic_only'] and raw['qualified_contracts'] == []
    assert set(raw['checks']) == set(cases) and len(cases) == 19
    workspace = path.parent/'workspace'
    assert read(workspace/'checks.json') == raw['checks']
    assert read(workspace/'runtime.json') == raw['runtime_sources']
    assert read(workspace/'host-inputs.json') == raw['host_inputs']
    for name, digest in raw['inputs'].items():
        assert sha(path.parent/'inputs'/name) == digest
        if name.startswith('src/dss/'):
            assert sha(workspace/'fixture'/name.removeprefix('src/')) == digest
    for name in ('command_group_cases.py', 'command_catalog_cases.py',
                 'command_group_controller.py', 'installed_provenance.py', 'command_group_provenance.py'):
        assert sha(workspace/name) == raw['inputs']['conformance/'+name]
    runtime = raw['runtime_sources']
    verify_capture(runtime['integrated'], raw['inputs'])
    if composed:
        assert overlay is None and raw['composed']
        assert runtime['profile'] == 'fresh-composed-display-command-wheel/1'
        assert raw['artifacts'] == {p.relative_to(workspace).as_posix(): sha(p) for p in workspace.rglob('*') if p.is_file()}
    else:
        assert runtime['profile'] == 'fresh-wheel-plus-display-command-catalog-and-group-overlays/1'
        record = runtime['overlay']
        assert record['files'] == {p.relative_to(overlay).as_posix(): sha(p)
                                  for p in overlay.rglob('*') if p.is_file() and p.name != 'base.json'}
        assert sha(overlay/'base.json') == runtime['base_sha256']
        base = read(overlay/'base.json')
        assert base['integrated'] == runtime['integrated'] and base['profile'] == runtime['base_profile']
        assert read(overlay/'manifest.json') == record['manifest']
        recipe = frozen('source_port/command_group_patches.py', revision)
        assert sha(overlay/'command_group_patches.py') == raw['inputs']['source_port/command_group_patches.py']
        assert set(recipe.PREIMAGES) == set(record['manifest'])
        expected = dict(base['installed'])
        for name, row in record['manifest'].items():
            before, after = overlay/'original'/name, overlay/'patched'/name
            assert sha(before) == expected[name] == row['preimage_sha256']
            assert recipe.apply(name, before.read_bytes()) == after.read_bytes()
            expected[name] = sha(after)
            assert expected[name] == row['sha256']
        additions = frozen('conformance/command_group_provenance.py', revision).ADDED
        assert set(record['added_sources']) == set(additions)
        for name, digest in record['added_sources'].items():
            assert name not in expected
            assert sha(overlay/'modules'/name) == digest == raw['inputs']['driver_plugin/src/'+name]
            expected[name] = digest
        assert runtime['installed'] == expected
    observations = {}
    for name, spec in cases.items():
        row = raw['checks'][name]
        project = workspace/name.replace(':', '-')
        assert row['passed'] and row['status'] == 'FINISHED'
        assert row['dimension'] == spec['dimension'] and row['source'] == spec['source']
        assert (project/'main.py').read_text(encoding='utf-8') == spec['source']
        assert read(project/'result.json') == row['result'] == {'completed': True}
        calls = row.get('observed', {}).get('calls', [])
        if calls:
            assert read(project/'observed.json') == row['observed']
        assert all(c.get('returned') is True and c.get('return_type') == 'bool'
                   for c in calls if 'returned' in c)
        assert sum('error_type' in c for c in calls) == (spec['dimension'] in ('failure', 'recovery'))
        assert sha(project/'native.log') == row['native_log_sha256']
        log = (project/'native.log').read_text(encoding='utf-8')
        assert 'AddressSanitizer:' not in log and 'runtime error:' not in log
        assert sha(project/'events.json') == row['events_sha256']
        events = read(project/'events.json')
        assert not any(e.get('event') == 'connectionError' or e.get('message', {}).get('id') == 'MSG_PROMPT' for e in events)
        native = [e['message']['fields'] for e in events
                  if e.get('message', {}).get('fields', {}).get('ItemType') == 'EXECUTION']
        receipts = row['receipts']
        assert len(receipts) == spec['expected_stages']
        assert row['initial_dss']['core']['commands_executed'] == 0
        assert row['final_dss']['core']['commands_executed'] == spec['expected_executions']
        assert row['final_dss']['core']['loaded_commands_count'] == spec['expected_loaded']
        with sqlite3.connect((project/'dss.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
            stored = db.execute('SELECT request_hash,raw_tc,acknowledgement FROM operations ORDER BY rowid').fetchall()
        assert len(stored) == len(receipts)
        frames, ack_hashes = [], {}
        for actual, saved in zip(stored, receipts):
            request_hash, packet, ack = actual
            assert request_hash == saved['request_hash'] and packet.hex() == saved['packet_hex']
            assert hashlib.sha256(packet).hexdigest() == saved['packet_sha256']
            ack = json.loads(ack)
            assert ack == saved['acknowledgement']
            frame = decode_tc(packet)
            assert frame['stage'] == ack['stage'] and frame['element_id'] == ack['element_id']
            ack_hashes[hashlib.sha256(canonical(ack)).hexdigest()] = ack
            if ack['stage'] == 'TRANSPORT' and ack['outcome'] == 'ACCEPTED':
                frames.append(frame)
        assert [e['command_name'] for f in frames for e in f.get('elements', [f])] == spec['expected_members']
        if name.startswith('Block'):
            assert len(frames) == 1 and 'elements' in frames[0] and row['uplink_groups'] == []
        if spec['dimension'] == 'encoding':
            expected_info = {'note': 'caf\u00e9 \u03bb \u9065\u6e2c'}
            assert all(e['additional_info'] == expected_info for f in frames for e in f.get('elements', [f]))
        with sqlite3.connect((project/'driver.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='command_results'").fetchone()
            results = [json.loads(r[0]) for r in db.execute('SELECT result FROM command_results ORDER BY rowid')] if exists else []
        assert results == row['member_results']
        for result in results:
            members = result['members']
            assert [m['index'] for m in members] == list(range(len(members)))
            assert [m['name'] for m in members] == (['CMD1', 'TC.SIMULATOR.RESET', 'CMD3']
                    if spec['dimension'] == 'failure' else spec['expected_members'])
            for member in members:
                assert member['uncertain'] is False
                for stage, outcome, digest in member['stages']:
                    ack = ack_hashes[digest]
                    assert (ack['stage'], ack['outcome']) == (stage, outcome)
                    assert ack['element_id'] == 'command-'+str(member['index'])
                    assert ack['operation_id'] == result['operation']
            if spec['dimension'] == 'failure':
                blocked = name.startswith('Block')
                assert [m['state'] for m in members] == ['SUCCEEDED', 'FAILED', 'LOADED' if blocked else 'NOT_SENT']
                assert members[2]['attempted'] is blocked
                last = [n for n in native if n['ItemName'] == 'CMD3'][-1]
                assert last['ItemStatus'] == 'IN PROGRESS'
                assert last['ItemValue'] == ('LOADING' if blocked else 'NOT_SENT')
            else:
                load = 'LoadOnly' in name
                assert all(m['state'] == ('LOADED' if load else 'SUCCEEDED') and m['attempted'] for m in members)
                finals = {n['ItemName']: n for n in native}
                assert all(n['ItemStatus'].split(',,') == ['SUCCESS']*len(n['ItemName'].split(',,')) for n in finals.values())
                assert all(set(n['ItemValue'].split(',,')) == {'LOADING' if load else 'ONBOARD_EXECUTION'} for n in finals.values())
        if 'Sequence' in name:
            sequence = [n for n in native if n['ItemName'].startswith('SEQ.DUPLICATE,,')][-1]
            assert sequence['ItemName'] == 'SEQ.DUPLICATE,,0@CMD1,,1@CMD1,,2@CMD2'
        if 'LoadOnly' in name:
            assert all(r['acknowledgement']['stage'] in ('TRANSPORT', 'LOADING') for r in receipts)
        if spec.get('competitor'):
            competitor = row['competitor']
            assert competitor['accepted'] is False and len(competitor['receipts']) == 1
            ack, = competitor['receipts']
            assert ack['outcome'] == 'REJECTED' and ack['detail']['reason'] == 'UPLINK_GROUP_BUSY'
            assert ack in [r['acknowledgement'] for r in receipts]
            assert competitor['before']['core'] == competitor['after']['core']
        if spec.get('clock') == 'ground':
            times = [r['acknowledgement']['simulation_time_ns'] for r in receipts
                     if r['acknowledgement']['stage'] == 'TRANSPORT' and r['acknowledgement']['outcome'] == 'ACCEPTED']
            assert times[0] >= 150000000 and times[1]-times[0] >= 150000000
        if name.startswith('Group'):
            group, = row['uplink_groups']
            assert group['frames'] == len(receipts)-bool(spec.get('competitor'))
            assert group['reason'] == ('DISCONNECTED' if spec['dimension'] == 'failure' else 'COMPLETED')
        observations[name] = dict(binary_stages=[r['acknowledgement']['stage'] for r in receipts],
            member_states=[[m['state'] for m in r['members']] for r in results],
            final_native=list({n['ItemName']: n for n in native}.values()),
            competitor_rejected=bool(spec.get('competitor')))
    return dict(passed=True, source_revision=revision, raw=ref(path), runtime_image=image,
        overlay_manifest=ref(overlay/'manifest.json') if overlay else None, observations=observations,
        artifacts={p.relative_to(workspace).as_posix(): sha(p) for p in workspace.rglob('*') if p.is_file()},
        qualified_contracts=[], full_v05_accepted=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--overlay', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = review(args.raw, args.overlay, args.revision, args.image)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, checks=len(result['observations']), output=str(args.output))))
