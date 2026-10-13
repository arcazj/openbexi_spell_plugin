"""Bind bounded native cancellation and unchanged full lifecycle evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import shutdown_pause_patches as patch


def sha(path):
    if os.name == 'nt':
        path = Path('\\\\?\\' + str(path.resolve()))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(path):
    path = path.resolve()
    raw = path.read_bytes()
    return dict(path=str(path), sha256=sha(path), bytes=len(raw),
                lf_sha256=hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest())


def record(model_path, gate_path, failed_pair_path):
    model = json.loads(model_path.read_bytes())
    gate = json.loads(gate_path.read_bytes())
    failed = json.loads(failed_pair_path.read_bytes())
    assert model['passed'] and model['candidate']['result'] == dict(tests=10, failures=0)
    assert model['baseline']['result'] == dict(tests=10, failures=5)
    expected_failures = {'already-finished', 'close-during-pause', 'close-during-interrupt',
                         'finish-during-pause', 'finish-during-interrupt'}
    assert {name for name, row in model['baseline']['scenarios'].items() if row['exit_code']} == expected_failures
    expected_names = {'already-closing', 'already-finished', 'pause-reached', 'interrupt-reached',
                      'close-during-pause', 'close-during-interrupt', 'finish-during-pause',
                      'finish-during-interrupt', 'real-timeout-with-noise', 'ordinary-wait-unchanged'}
    for profile in ('baseline', 'candidate'):
        assert set(model[profile]['scenarios']) == expected_names
        assert model[profile]['compile_exit_code'] == 0
        assert sha(model_path.parent / (profile + '-probe')) == model[profile]['binary_sha256']
        assert sha(model_path.parent / (profile + '-build.log')) == model[profile]['compile_log_sha256']
        parsed_cases = []
        for scenario, row in model[profile]['scenarios'].items():
            path = model_path.parent / (profile + '-' + scenario + '.log')
            assert sha(path) == row['log_sha256']
            failure = int(profile == 'baseline' and scenario in expected_failures)
            assert row['exit_code'] == failure and row['result'] == dict(tests=1, failures=failure)
            raw = path.read_text()
            summaries = re.findall(r'^\{"tests":\d+,"failures":\d+\}$', raw, re.M)
            assert len(summaries) == 1 and json.loads(summaries[0]) == row['result']
            cases = re.findall(r'^CASE ([^\n]+)$', raw, re.M)
            assert len(cases) == 1
            if failure:
                assert cases[0].startswith(scenario + ' FAIL ')
            else:
                assert cases[0] == scenario + ' PASS'
            assert 'AddressSanitizer:' not in raw and 'runtime error:' not in raw
            parsed_cases.extend(cases)
        assert parsed_cases == model[profile]['cases']
    compiled_path = model_path.parent / 'compiled/incremental-build.json'
    assert sha(compiled_path) == model['incremental_build_sha256']
    compiled = json.loads(compiled_path.read_bytes())
    assert compiled['passed'] and set(compiled['units']) == {patch.SOURCE}
    assert set(compiled['artifacts']) == {'SPELL-Context'}
    unit = compiled['units'][patch.SOURCE]
    assert unit['exit_code'] == 0 and unit['original_sha256'] == patch.PORTED
    assert unit['patched_sha256'] == model['source']['patched_sha256']
    assert sha(compiled_path.parent / unit['object']) == unit['object_sha256']
    artifact = compiled['artifacts']['SPELL-Context']
    assert artifact['exit_code'] == 0
    assert artifact['original_sha256'] == model['prior_artifact']['SPELL-Context']
    assert artifact['sha256'] == model['artifact']['SPELL-Context'] == sha(compiled_path.parent / 'SPELL-Context')
    assert gate['passed'] and gate['exit_code'] == 0
    native = gate['native']
    assert native['passed'] and native['exit_code'] == 0
    assert native['patch_manifest_sha256'] == sha(model_path)
    assert native['patch'] == model
    assert native['native_sha256'] == model['artifact']['SPELL-Context']
    assert native['qualifier_sha256'] == sha(ROOT / 'source_port/qualify_context.py')
    expected = dict(tests=10, failures=0, errors=0, skips=0, lifecycle_runs=25, service_checkpoint_rejections=2)
    assert all(native['gate'][name] == value for name, value in expected.items())
    assert len(set(native['gate']['completed_lifecycles'])) == 25
    for path, expected_sha in native['outputs'].items():
        assert sha(gate_path.parent / 'shutdown-context-gate' / path) == expected_sha
    assert gate['inputs']['conformance/shutdown_pause_gate.py'] == sha(ROOT / 'conformance/shutdown_pause_gate.py')
    assert native['inputs']['shutdown_pause_gate.py'] == gate['inputs']['conformance/shutdown_pause_gate.py']
    if 'collection_recovery' in gate:
        collection = gate['collection_recovery']
        assert collection['collector_sha256'] == sha(ROOT / 'conformance/collect_shutdown_pause.py')
        assert sha(Path(collection['original_report']['path'])) == collection['original_report']['sha256']
        assert sha(gate_path.parent / 'native-evidence.tar') == gate['archive']['sha256']
    for name, path in [('shutdown_pause_patches.py', 'source_port/shutdown_pause_patches.py'),
                       ('shutdown_pause.cpp', 'conformance/shutdown_pause.cpp'),
                       ('shutdown_pause_build.py', 'conformance/shutdown_pause_build.py'),
                       ('incremental_native.py', 'distribution/incremental_native.py')]:
        assert model['inputs'][name] == sha(ROOT / path)
    for label, expected_sha in [('original', patch.ORIGINAL), ('ported', patch.PORTED),
                               ('patched', model['source']['patched_sha256'])]:
        assert sha(model_path.parent / label / patch.SOURCE) == expected_sha
    original = (model_path.parent / 'original' / patch.SOURCE).read_bytes()
    ported = (model_path.parent / 'ported' / patch.SOURCE).read_bytes()
    assert patch.apply(patch.SOURCE, original, ported) == (model_path.parent / 'patched' / patch.SOURCE).read_bytes()
    assert failed['accepted'] is False and failed['all_native_artifacts_identical']
    assert failed['context']['failures'] == 1 and failed['executor']['failures'] == 0
    assert failed['artifacts']['SPELL-Context']['b_sha256'] == model['prior_artifact']['SPELL-Context']
    paths = ['source_port/shutdown_pause_patches.py', 'conformance/shutdown_pause.cpp',
             'conformance/shutdown_pause_build.py', 'conformance/shutdown_pause_gate.py',
             'conformance/shutdown_pause.Dockerfile', 'conformance/shutdown_pause.Dockerfile.dockerignore',
             'conformance/record_shutdown_pause.py', 'tests/test_shutdown_pause_recipe.py',
             'conformance/collect_shutdown_pause.py',
             'source_port/native_patches.py', 'source_port/qualify_context.py', 'distribution/incremental_native.py']
    return dict(schema='openbexi.spell.shutdown-pause-review/1', passed=True,
                profile='original-native-context-executor; Linux amd64 CPython3.13 ASAN/UBSAN',
                image=gate['image'], source=model['source'], artifacts=model['artifact'],
                evidence=dict(failed_pair=bound(failed_pair_path), model=bound(model_path), context=bound(gate_path)),
                inputs={path: hashlib.sha256((ROOT / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for path in paths},
                raw_inputs={path: sha(ROOT / path) for path in paths},
                qualified_rows=[], full_v05_accepted=False, full_v06_accepted=False,
                limitations=[model['limitation'],
                    'Cancellation observes close/process-terminal flags in bounded requested event waits; this is not a hard real-time guarantee.',
                    'Out-of-order status delivery and the command/check race are unchanged.',
                    'Diagnostic overlay only: a newly reviewed composition and two complete independent wheel builds are still required.',
                    'The separate child lifecycle recipe changes another block of this source and needs explicit checked composition ordering.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--failed-pair', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'conformance/evidence/shutdown_pause_review.json')
    args = parser.parse_args()
    report = record(args.model, args.context, args.failed_pair)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', newline='\n')
    print(json.dumps({'passed': True, 'output': str(args.output), 'sha256': sha(args.output)}))


if __name__ == '__main__':
    main()
