"""Bind serialized child lifecycle evidence without promoting language rows."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    path = Path(path).resolve(strict=True)
    return json.loads(path.read_bytes()), dict(path=str(path), sha256=sha(path))


def qualify_run(path, image, suite):
    raw, reference = read(path)
    assert raw['passed'] is True and raw['exit_code'] == 0
    assert raw['image'] == image
    assert not raw.get('expect_host_rejection')
    assert bool(raw.get('externally_removed')) == (suite == 'removed')
    assert bool(raw.get('reopen')) == (suite == 'reopen')
    for name, expected in raw['inputs'].items():
        assert sha(ROOT/'conformance'/name) == expected, name
    assert sha(Path(path).parent/'workspace.tar') == raw['workspace_sha256']
    observed = raw['observed']
    assert observed['passed'] is True
    expected = {operation+'-'+phase for operation in ('close', 'kill')
                for phase in (('prompt', 'finished', 'none') if suite == 'lifecycle'
                              else ('prompt', 'finished'))}
    assert set(observed['cases']) == expected
    for name, row in observed['cases'].items():
        assert row['passed'] is True, name
        assert not any(key.endswith('_error') or key == 'error' for key in row), name
    return observed, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'lifecycle', 'removed', 'reopen', 'executor-gate',
                 'context-gate', 'baseline', 'relay-failure', 'debug-report', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    build, build_ref = read(args.build)
    assert build['passed'] is True and build['full_v06_accepted'] is False
    for name, expected in build['inputs'].items():
        assert sha(ROOT/name) == expected, name
    runs = [qualify_run(path, build['image'], suite) for suite, path in
            (('lifecycle', args.lifecycle), ('removed', args.removed), ('reopen', args.reopen))]
    runtime = runs[0][0]['runtime_sources']
    assert all(observed['runtime_sources'] == runtime for observed, _ in runs)
    host = runs[0][0]['host_inputs']
    assert all(observed['host_inputs'] == host for observed, _ in runs)
    # The diagnostic base deliberately uses the separately qualified child
    # host donor. Do not mislabel older host files in this branch as installed.
    donor = '166caff449f208d41859d41257517fc8fec6f509'
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', donor,
                                    'host_runtime/python'], cwd=ROOT, text=True).splitlines()
    expected_host = {Path(name).name: hashlib.sha256(subprocess.check_output(
        ['git', 'show', donor+':'+name], cwd=ROOT)).hexdigest()
        for name in names if name.endswith('.py')}
    assert host == expected_host
    overlay = runtime['child_lifecycle_overlay']
    assert overlay['mode'] == 'child-lifecycle'
    sys.path.insert(0, str(ROOT/'source_port'))
    import child_lifecycle_patches as patch
    import native_patches
    import zipfile
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as bundle:
        expected_sources = {}
        for name in patch.PREIMAGES:
            original = bundle.read(name)
            ported = native_patches.apply(name, original)
            patched = patch.apply(name, original, ported)
            expected_sources[name] = {label+'_sha256': hashlib.sha256(content).hexdigest()
                for label, content in (('original', original), ('ported', ported), ('patched', patched))}
    assert overlay['sources'] == expected_sources
    assert set(overlay['artifacts']) == {'libspell_executor313.so', 'SPELL-Context'}
    for name, expected in overlay['recipes'].items():
        folder = 'source_port' if name == 'child_lifecycle_patches.py' else (
            'distribution' if name == 'incremental_native.py' else 'conformance')
        assert sha(ROOT/folder/name) == expected, name
    gates = {}
    for name, path, count in (('executor', args.executor_gate, 23), ('context', args.context_gate, 10)):
        gate, reference = read(path)
        assert gate['native_image'] == build['native_image']
        assert gate['controller_exit_code'] == gate['exit_code'] == 0
        assert gate['overlay'] == overlay and gate['native_artifacts'] == overlay['artifacts']
        assert gate['gate_name'] == name and gate['gate']['tests'] == count
        assert all(gate['gate'][key] == 0 for key in ('failures', 'errors', 'skips'))
        assert gate['qualifier_sha256'] == sha(ROOT/'source_port'/('qualify_'+name+'.py'))
        assert gate['controller_sha256'] == sha(ROOT/'conformance/child_lifecycle_gate.py')
        gates[name] = dict(report=reference, results=gate['gate'])
    baseline, baseline_ref = read(args.baseline)
    assert baseline['passed'] is False and len(baseline['observed']['cases']) == 4
    assert all(row['passed'] is False and row.get('parent_result') == {'returned': True}
               for row in baseline['observed']['cases'].values())
    relay, relay_ref = read(args.relay_failure)
    assert relay['passed'] is False
    assert sum(row['passed'] is True for row in relay['observed']['cases'].values()) == 2
    debug, debug_ref = read(args.debug_report)
    assert debug['image'] == relay['image']
    stacks = sorted(args.debug_report.parent.glob('stack-*.log'))
    assert len(stacks) >= 3
    combined = '\n'.join(path.read_text(encoding='utf-8') for path in stacks)
    assert all(symbol in combined for symbol in ('SPELLipcServerInterface::getChannel',
        'SPELLexecutor::forwardRequestToClient', 'Peer::processRequest'))
    inputs = {p.relative_to(ROOT).as_posix(): sha(p) for p in
        [*sorted((ROOT/'conformance').glob('*child_lifecycle*')),
         ROOT/'source_port/child_lifecycle_patches.py', ROOT/'distribution/incremental_native.py']
        if p.is_file()}
    report = dict(schema='openbexi.spell.child-lifecycle/1', qualified_contracts=[],
        full_v05_accepted=False, full_v06_accepted=False, image=build['image'],
        build=build_ref, runs={name: reference for name, (_, reference) in
            zip(('lifecycle', 'removed', 'reopen'), runs)}, native_controls=14,
        runtime_sources=runtime, host_donor=donor, host_inputs=host, inputs=inputs,
        gates=gates, baseline=baseline_ref, abandoned_gui_relay=relay_ref,
        deadlock=dict(report=debug_ref, stacks=[dict(path=str(p.resolve()), sha256=sha(p)) for p in stacks]),
        scope=['Correct child identity and confirmed native context close/kill',
               'Serialized PROMPT/FINISHED/no-child and replacement-child controls',
               'Rejected operations preserve target identity across two explicit attempts'],
        exclusions=['General concurrent child replacement and notification races',
                    'Timeout/uncertain-effect fault injection beyond explicit rejected controls',
                    'Original Eclipse GUI compatibility and shared native SPELL debugging',
                    'Diagnostic overlay preserves original RECORD; fresh distribution remains separate'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.output), sha256=sha(args.output), native_controls=14)))


if __name__ == '__main__':
    main()
