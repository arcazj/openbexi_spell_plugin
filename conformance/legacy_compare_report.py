"""Verify native comparison diagnostics without accepting an overlaid release."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid
import zipfile

from installed_provenance import verify_capture
from legacy_compare_cases import CASES, INVALID, FIXTURE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import legacy_compare_patches as patch

RECIPES = {'legacy_compare_patches.py': 'source_port/legacy_compare_patches.py',
           'legacy_compare_syntax.py': 'source_port/legacy_compare_syntax.py',
           'legacy_compare_build.py': 'conformance/legacy_compare_build.py',
           'incremental_native.py': 'distribution/incremental_native.py'}
ARTIFACTS = {'libspell_executor313.so', 'SPELL-Context', 'SPELL-Listener'}
EXPECTED_FAILURES = set(CASES) - {'modern-control'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return {'path': str(path.resolve()), 'sha256': sha(path)}


def exact(row):
    path = Path(row['path'])
    assert sha(path) == row['sha256'], path
    return path, json.loads(path.read_bytes())


def verify_archive(path, report, original):
    assert set(report['checks']) == set(CASES) | set(INVALID)
    failures = {name for name, row in report['checks'].items() if not row['passed']}
    assert failures == (EXPECTED_FAILURES if original else set())
    assert report['passed'] is (not original)
    assert report['controller_exit_code'] == int(original)
    with tarfile.open(path.parent / 'workspace.tar') as archive:
        members = {item.name.removeprefix('./'): item for item in archive if item.isfile()}
        read = lambda name: archive.extractfile(members[name]).read()
        assert json.loads(read('checks.json')) == report['checks']
        assert json.loads(read('runtime.json')) == report['runtime_sources']
        for name, source in {**CASES, **INVALID}.items():
            row = report['checks'][name]
            assert row['source'] == source, name
            suffix = "\nfrom spell.lang.functions import Display\nDisplay('LEGACY_COMPARE_PASSED')\n" if name in CASES else ''
            assert read(name + '/data/Procedures/main.py').decode('utf-8') == source + suffix
            assert read(name + '/data/Procedures/comparison_fixture.py').decode('utf-8') == FIXTURE
            log = read(name + '/native.log')
            assert b'AddressSanitizer:' not in log and b'runtime error:' not in log, name
            if name in INVALID or (original and name in EXPECTED_FAILURES):
                assert b'SyntaxError' in log and b'LEGACY_COMPARE_PASSED' not in log, name
            else:
                assert row['exit_code'] == 0
                assert b'[ STATUS  ] FINISHED' in log and b'LEGACY_COMPARE_PASSED' in log, name


def verify_export(directory, baseline, candidate):
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    assert manifest == candidate['overlay'] and manifest['passed'] is True
    assert json.loads((directory / 'baseline.json').read_bytes()) == {
        key: baseline[key] for key in ('integrated', 'installed')}
    assert baseline['overlay'] is None and candidate['integrated'] == baseline['integrated']
    assert set(manifest['sources']) == set(patch.PREIMAGES)
    assert set(manifest['recipes']) == set(RECIPES)
    assert set(manifest['artifacts']) == set(manifest['original_artifacts']) == ARTIFACTS
    compiled_path = directory / 'compiled/incremental-build.json'
    assert sha(compiled_path) == manifest['incremental_build_sha256']
    compiled = json.loads(compiled_path.read_bytes())
    assert compiled['passed'] and not compiled['full_qualification_passed']
    assert set(compiled['units']) == set(patch.PREIMAGES)
    assert set(compiled['artifacts']) == ARTIFACTS
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        for name, row in manifest['sources'].items():
            original, ported, patched = (directory.joinpath(label, name).read_bytes()
                                         for label in ('original', 'ported', 'patched'))
            assert original == archive.read(name)
            assert patched == patch.apply(name, original, ported)
            for label in ('original', 'ported', 'patched'):
                assert sha(directory / label / name) == row[label + '_sha256']
            unit = compiled['units'][name]
            assert unit['exit_code'] == 0
            assert unit['original_sha256'] == row['ported_sha256']
            assert unit['patched_sha256'] == row['patched_sha256']
    expected = dict(baseline['installed'])
    for name, digest in manifest['artifacts'].items():
        destination = 'spell_native/bin/' + name
        assert expected[destination] == manifest['original_artifacts'][name]
        assert digest != expected[destination] and sha(directory / 'compiled' / name) == digest
        assert compiled['artifacts'][name]['sha256'] == digest
        assert compiled['artifacts'][name]['exit_code'] == 0
        expected[destination] = digest
    assert candidate['installed'] == expected, 'Undeclared installed payload change'
    for name, source in RECIPES.items():
        assert sha(directory / name) == manifest['recipes'][name] == sha(ROOT / source)
    return manifest


def qualify(build_path, directory):
    build = json.loads(build_path.read_bytes())
    assert build['passed'] and build['state'] == 'completed'
    expected_exits = {'baseline': 1, 'native-base': 0, 'overlay-build': 0, 'candidate': 0}
    assert set(build['stages']) == set(expected_exits)
    for name, stage in build['stages'].items():
        assert stage['exit_code'] == expected_exits[name], name
        assert sha(Path(stage['log']['path'])) == stage['log']['sha256']
    baseline_path, baseline = exact(build['baseline'])
    candidate_path, candidate = exact(build['candidate_evidence'])
    assert baseline['runtime_image'] == build['base_image']
    assert candidate['runtime_image'] == build['candidate']['image']
    assert baseline['inputs'] == candidate['inputs']
    for name, digest in candidate['inputs'].items():
        assert sha(ROOT / name) == digest, name
    for path, raw, original in ((baseline_path, baseline, True), (candidate_path, candidate, False)):
        verify_capture(raw['runtime_sources']['integrated'], raw['inputs'])
        verify_archive(path, raw, original)
    manifest = verify_export(directory, baseline['runtime_sources'], candidate['runtime_sources'])
    return dict(schema='openbexi.spell.legacy-comparison-diagnostic/1', passed=True,
        runtime_image=candidate['runtime_image'], baseline_image=baseline['runtime_image'],
        inputs={**candidate['inputs'], 'conformance/legacy_compare_report.py': sha(Path(__file__))},
        sources=manifest['sources'], recipes=manifest['recipes'], native_artifacts=manifest['artifacts'],
        build=reference(build_path), diagnostic_manifest=reference(directory / 'manifest.json'),
        baseline={**reference(baseline_path), 'workspace_sha256': sha(baseline_path.parent / 'workspace.tar')},
        candidate={**reference(candidate_path), 'workspace_sha256': sha(candidate_path.parent / 'workspace.tar')},
        retained_baseline_failures=sorted(EXPECTED_FAILURES), passed_checks=len(candidate['checks']),
        qualified_contracts=[],
        scope='Native procedure compiler and AST analyzer compatibility for the legacy <> token',
        limitations=['Diagnostic overlay; fresh composed wheels and full regressions remain required',
                     'Imported Python modules, eval and compile retain CPython syntax; parent language sections are not qualified'],
        full_v05_accepted=False, full_v06_accepted=False, stable_v1_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    args = parser.parse_args()
    build = json.loads(args.build.read_bytes())
    assert build['passed']
    directory = ROOT / '.qualification/legacy-compare-export' / uuid.uuid4().hex
    directory.mkdir(parents=True)
    name = 'openbexi-legacy-evidence-' + uuid.uuid4().hex
    try:
        subprocess.run(['docker', 'create', '--name', name, '--network=none', '--entrypoint', 'true',
                        build['candidate']['image']], check=True, capture_output=True)
        subprocess.run(['docker', 'cp', name + ':/opt/legacy-compare-patch/.', str(directory)],
                       check=True, capture_output=True)
    finally:
        subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
    report = qualify(args.build, directory)
    output = ROOT / 'conformance/evidence/legacy_compare.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(output), 'passed': True, 'checks': report['passed_checks']}))


if __name__ == '__main__':
    main()
