"""Bind listener state-race diagnostics to exact source and native IPC evidence."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid
import zipfile

from context_snapshot_provenance import RECIPES, qualification_identity
from context_snapshot_probe import PRELUDE, MAIN, methods

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'source_port'), str(ROOT / 'distribution')]
import native_patches
import context_snapshot_patches as patch
from run_language_regressions import validate_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return dict(path=str(path.resolve()), sha256=sha(path))


def constant(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    return next(ast.literal_eval(row.value) for row in tree.body if isinstance(row, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in row.targets))


def verify_export(directory, runtime):
    overlay = runtime['context_snapshot_overlay']
    base = runtime['baseline']
    assert json.loads((directory / 'manifest.json').read_bytes()) == overlay
    assert json.loads((directory / 'baseline-installed.json').read_bytes()) == base
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    ported = native_patches.apply(patch.SOURCE, original)
    patched = patch.apply(patch.SOURCE, original, ported)
    for label, content, field in [('original',original,'original_sha256'),
            ('ported',ported,'preimage_sha256'), ('patched',patched,'patched_sha256')]:
        path = directory / (label + '.C')
        assert path.read_bytes() == content and sha(path) == overlay[field]
    assert overlay['source'] == patch.SOURCE and overlay['passed'] and not overlay['full_release_accepted']
    compiled_path = directory / 'compiled/incremental-build.json'
    assert sha(compiled_path) == overlay['incremental_build_sha256']
    compiled = json.loads(compiled_path.read_bytes())
    assert compiled['passed'] and not compiled['full_qualification_passed']
    assert set(compiled['units']) == {patch.SOURCE}
    unit = compiled['units'][patch.SOURCE]
    assert unit['exit_code'] == 0 and unit['original_sha256'] == patch.PORTED
    assert unit['patched_sha256'] == overlay['patched_sha256']
    assert set(compiled['artifacts']) == set(overlay['artifacts']) == set(overlay['original_artifacts']) == {'SPELL-Listener'}
    artifact = compiled['artifacts']['SPELL-Listener']
    assert artifact['exit_code'] == 0
    assert artifact['original_sha256'] == overlay['original_artifacts']['SPELL-Listener'] == base['native_artifacts']['SPELL-Listener']
    assert sha(directory / 'compiled/SPELL-Listener') == artifact['sha256'] == overlay['artifacts']['SPELL-Listener']
    assert artifact['sha256'] != artifact['original_sha256']
    assert set(overlay['recipes']) == set(RECIPES)
    for name, source in RECIPES.items():
        assert sha(directory / name) == overlay['recipes'][name] == sha(ROOT / source)
    assert compiled['recipe_sha256'] == overlay['recipes']['incremental_native.py']
    probes = overlay['probes']
    assert json.loads((directory / 'probes/result.json').read_bytes()) == probes
    assert sha(directory / 'probes/result.json') == overlay['probes_sha256']
    assert probes['passed'] and probes['preimage_sha256'] == patch.PORTED
    assert probes['patched_sha256'] == overlay['patched_sha256']
    assert set(probes['probes']) == {'original','patched'}
    for label, source in (('original',ported), ('patched',patched)):
        row = probes['probes'][label]
        folder = directory / 'probes'
        assert (folder / (label + '.C')).read_bytes() == source
        probe = folder / (label + '-probe.cpp')
        assert probe.read_text(encoding='utf-8') == PRELUDE + methods(source) + MAIN
        assert sha(probe) == row['source_sha256']
        assert sha(folder / (label + '-probe')) == row['binary_sha256']
        assert json.loads((folder / (label + '-run.log')).read_bytes()) == row['observation']
        assert row['exit_code'] == (1 if label == 'original' else 0)
        observation = row['observation']
        assert observation == dict(port='0', status='RUNNING' if label == 'original' else 'AVAILABLE',
            update_completed_during_read=label == 'original', coherent=label == 'patched',
            subsequent_current=True, unknown_context_rejected=True)
    return overlay


def verify_archive(path, raw, kind):
    with tarfile.open(path.parent / 'workspace.tar') as archive:
        files = {entry.name.removeprefix('./'):entry for entry in archive if entry.isfile()}
        read = lambda name: archive.extractfile(files[name]).read()
        assert json.loads(read('checks.json')) == raw['checks']
        assert json.loads(read('runtime.json')) == raw['runtime_sources']
        if kind == 'startup':
            source = constant(ROOT / 'conformance/context_snapshot_startup.py', 'SOURCE')
            assert raw['options'] == {'repeat':40}
            assert set(raw['checks']) == {'startup-' + str(n).zfill(3) for n in range(40)}
            for name, row in raw['checks'].items():
                assert read(name + '/main.py').decode() == source
                assert hashlib.sha256(source.encode()).hexdigest() == row['procedure_sha256']
                assert read(name + '/startup-result.txt') == b'STARTUP_SNAPSHOT_PASSED'
                log = read(name + '/native.log')
                assert b'AddressSanitizer:' not in log and b'runtime error:' not in log
                assert row['final']['ExecutorStatus'] == 'FINISHED'
                assert row['missing']['ContextStatus'] == 'ERROR' and row['missing']['ContextPort'] == '0'
                assert row['current']['ContextStatus'] == 'RUNNING' and 1 <= int(row['current']['ContextPort']) <= 65535
                assert len(row['observations']) >= 3
                for observation in row['observations']:
                    response = observation['response']
                    if response['ContextStatus'] == 'RUNNING':
                        assert 1 <= int(response['ContextPort']) <= 65535
        for row in raw['checks'].values():
            assert row['passed'] and not any(row.get(field) for field in
                ('error','cleanup_error','extra_cleanup_error','drain_error','sanitizer_failure'))
            assert 'AddressSanitizer:' not in row.get('log','') and 'runtime error:' not in row.get('log','')


def qualify(paths, directory, failure_path, source_revision=None):
    raws = {kind:json.loads(path.read_bytes()) for kind,path in paths.items()}
    assert set(paths) == {'errors','recovery','startup'}
    runtime = raws['startup']['runtime_sources']
    image = raws['startup']['runtime_image']
    inputs = {}
    for kind, count in [('errors',8),('recovery',22),('startup',40)]:
        raw, path = raws[kind], paths[kind]
        if source_revision is None:
            validate_report(path, image, count)
        else:
            # Diagnostic history remains verifiable after the composition changes.
            # This never substitutes for validation of a newly composed runtime.
            assert raw['runtime_image'] == image and raw.get('controller_exit_code', 0) == 0
            assert raw['inputs']
            for name, digest in raw['inputs'].items():
                content = subprocess.check_output(['git', 'show', source_revision + ':' + name], cwd=ROOT)
                assert hashlib.sha256(content).hexdigest() == digest, name
        assert raw['passed'] and len(raw['checks']) == count and raw['runtime_sources'] == runtime
        qualification_identity(runtime, raw['inputs'], raw.get('lf_normalized_inputs'))
        verify_archive(path, raw, kind)
        for name, digest in raw['inputs'].items():
            assert name not in inputs or inputs[name] == digest
            inputs[name] = digest
    assert raws['recovery']['options']['modes'] == raws['errors']['options']['modes'] == ['ON_LINE','ON_STEP']
    overlay = verify_export(directory, runtime)
    failure = json.loads(failure_path.read_bytes())
    assert not failure['passed'] and len(failure['checks']) == 22
    assert {k for k,row in failure['checks'].items() if not row['passed']} == {'ON_LINE:two-instances'}
    row = failure['checks']['ON_LINE:two-instances']
    assert row['error'] == "BridgeConnectionError('Native IPC startup deadline expired')"
    assert not row.get('sanitizer_failure') and 'checkpoint' not in row
    assert failure['runtime_sources']['native_artifacts'] == runtime['baseline']['native_artifacts']
    for name, digest in failure['inputs'].items():
        content = subprocess.check_output(['git','show','ddd58e8:' + name], cwd=ROOT)
        assert hashlib.sha256(content).hexdigest() == digest, name
    for name in ('conformance/context_snapshot_report.py','tests/test_context_snapshot_report.py'):
        inputs[name] = sha(ROOT / name)
    return dict(passed=True, runtime_image=image, baseline_image=failure['runtime_image'], inputs=inputs,
        source=overlay['source'], original_sha256=overlay['original_sha256'], preimage_sha256=overlay['preimage_sha256'],
        patched_sha256=overlay['patched_sha256'], recipes=overlay['recipes'], native_artifacts=overlay['artifacts'],
        probes=overlay['probes'], export=dict(path=str(directory.resolve()), manifest_sha256=sha(directory / 'manifest.json')),
        raw={kind:{**reference(path), 'workspace_sha256':sha(path.parent / 'workspace.tar')} for kind,path in paths.items()},
        retained_failure={**reference(failure_path), 'workspace_sha256':sha(failure_path.parent / 'workspace.tar')},
        passed_checks=dict(errors=8,recovery=22,startup=40), qualified_contracts=[],
        scope='Coherent listener context metadata, with exact-method interleaving controls and real IPC startup/recovery',
        limitations=['The retained startup failure did not log the requested port; the controlled probe independently demonstrates the torn-snapshot defect.',
            'Diagnostic one-binary overlay; fresh composed packages and full regressions remain required.'],
        full_v05_accepted=False, full_v06_accepted=False, stable_v1_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('errors','recovery','startup','failure'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    paths = {name:getattr(args,name) for name in ('errors','recovery','startup')}
    image = json.loads(args.startup.read_bytes())['runtime_image']
    directory = ROOT / '.qualification/context-snapshot-export' / uuid.uuid4().hex
    directory.mkdir(parents=True)
    container = 'openbexi-snapshot-export-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker','create','--name',container,'--network=none','--entrypoint','true',image], check=True, capture_output=True)
        subprocess.run(['docker','cp',container+':/opt/context-snapshot-patch/.',str(directory)], check=True, capture_output=True)
    finally:
        subprocess.run(['docker','rm',container], check=True, capture_output=True)
    report = qualify(paths, directory, args.failure)
    output = ROOT / 'conformance/evidence/context_snapshot.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), passed=True, checks=report['passed_checks'])))


if __name__ == '__main__':
    main()
