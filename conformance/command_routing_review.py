"""Review the retained malformed Block counterexample and its native correction."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'distribution'), str(ROOT/'driver_plugin/src')]
from evidence_sources import source_bytes
from run_language_regressions import validate_report
from installed_provenance import verify_capture
from openbexi_spell_dss.codec import unpack
from openbexi_spell_dss.stubs import SPELLDriver_pb2 as p
from google.protobuf.message_factory import GetMessageClass

SOURCE = 'driver_plugin/src/openbexi_dss_proxy/command_group.py'
BEFORE = '377231c7a9136d94b1e8c7290b0326ddaeb4d4c3'
AFTER = 'd9ad9f08a8502388cc0723825ec64f68cfe8e6ae'
CASE = 'invalid-block:failure'
BASELINE = ROOT/'.qualification/v0.5/cmd/7701bee94ed34fa5aad0c202a544ecf7/result.json'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
ref = lambda path: dict(path=str(path.resolve()), sha256=sha(path))


def capture(path, revision):
    raw = read(path)
    assert raw['controller_exit_code'] == 0
    assert raw['observations']['passed'] and raw['observations']['status'] == 'FINISHED'
    for name, digest in raw['inputs'].items():
        assert hashlib.sha256(source_bytes(ROOT, name, revision)).hexdigest() == digest, name
    verify_capture(raw['runtime_sources']['integrated'], raw['inputs'], raw['lf_normalized_inputs'])
    workspace = path.parent/'workspace'
    assert read(workspace/'observations.json') == raw['observations']
    assert read(workspace/'runtime.json') == raw['runtime_sources']
    checks = read(workspace/'procedure/checks.json')
    assert set(checks) == set(raw['checks'])
    for name, row in checks.items():
        assert all(raw['checks'][name][key] == value for key, value in row.items())
    cases = read(workspace/'procedure/cases.json')
    namespace = {}
    exec(compile(source_bytes(ROOT, 'conformance/cmd_cases.py', revision), 'cmd_cases.py', 'exec'), namespace)
    assert cases == namespace['CASES']
    assert all(raw['checks'][name]['source'] == code for name, code in cases.items())
    files = ('controller.py', 'installed_provenance.py', 'observations.json', 'runtime.json',
             'native.log', 'driver.sqlite', 'dss.sqlite', 'procedure/checks.json',
             'procedure/cases.json', 'procedure/cmd_contracts.py')
    return raw, {name: sha(workspace/name) for name in files}


def review(path, image, revision):
    assert sha(BASELINE) == 'ad4935996fb532d9d4f6c4f1c9ea1078b8354b849c7c61c1efe49c65b3934350'
    before = source_bytes(ROOT, SOURCE, BEFORE)
    after = source_bytes(ROOT, SOURCE, AFTER)
    old = b'def settings(item,config):return dict(config or {},**item.getConfig())'
    new = b'''def settings(item,config):
    local = item.getConfig()
    # TcInterface chooses its block path from the call configuration before
    # applying item overrides. Validate both sources so an item default cannot
    # hide a malformed flag that already selected a different transport path.
    for options in (config or {}, local):
        for name in ('Block', 'Group'):
            if name in options and type(options[name]) is not bool:
                raise DriverException(name+' must be boolean')
    return dict(config or {},**local)'''
    assert before.count(old) == 1 and before.replace(old, new) == after
    assert source_bytes(ROOT, SOURCE, revision) == after == (ROOT/SOURCE).read_bytes()
    baseline, baseline_files = capture(BASELINE, BEFORE)
    assert len(baseline['checks']) == 54
    assert [name for name, row in baseline['checks'].items() if not row['passed']] == [CASE]
    assert baseline['checks'][CASE]['error'] == 'AssertionError: Expected DriverException'
    calls = [row for row in baseline['observations']['rpc'] if row['check'] == CASE and row['path'].endswith('/SendBlock')]
    call, = calls
    shape = p.DESCRIPTOR.services_by_name['SPELLDriverInterface_TC'].methods_by_name['SendBlock'].input_type
    request = GetMessageClass(shape).FromString(bytes.fromhex(call['request']))
    token = unpack(request.config)['_OpenBEXICommandGroup']
    assert call['response'] == '0801'
    with sqlite3.connect((BASELINE.parent/'workspace/driver.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        results = [json.loads(row[0]) for row in db.execute('SELECT result FROM command_results')]
    result, = [row for row in results if row['token'] == token]
    assert result['outcome'] == 'SUCCEEDED'
    assert [row['name'] for row in result['members']] == ['CMD1', 'CMD2']
    assert all(row['state'] == 'SUCCEEDED' for row in result['members'])
    operations = [row for row in baseline['observations']['evidence']['operations']
                  if row['operation_id'] == result['operation']]
    assert len(operations) == 9 and sum(row['acknowledgement']['stage'] == 'ONBOARD_EXECUTION' for row in operations) == 2
    validate_report(path, image, 54, source_revision=revision)
    fixed, fixed_files = capture(path, revision)
    assert len(fixed['checks']) == 54 and fixed['checks'][CASE]['source'] == baseline['checks'][CASE]['source']
    assert fixed['checks'][CASE]['passed']
    assert not any(row['check'] == CASE and '_TC/Send' in row['path'] for row in fixed['observations']['rpc'])
    expected = hashlib.sha256(after).hexdigest()
    installed = fixed['runtime_sources']['integrated']['driver_composition']['manifest']['python_sources']
    assert installed[SOURCE.removeprefix('driver_plugin/src/')] == expected
    return dict(passed=True, baseline=ref(BASELINE), candidate=ref(path), runtime_image=image,
        source_revision=revision, previous_source_revision=BEFORE, correction_revision=AFTER,
        source=SOURCE, before_sha256=hashlib.sha256(before).hexdigest(), after_sha256=expected,
        baseline_artifacts=baseline_files, candidate_artifacts=fixed_files,
        observed_failure='Malformed call-level Block flag caused two actual command executions',
        observed_recovery='Same native call rejects before any TC effect RPC; all 54 command checks pass',
        full_v05_accepted=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    result = review(args.raw, args.image, args.revision)
    target = ROOT/'conformance/evidence/command_routing_validation.json'
    target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, output=str(target))))
