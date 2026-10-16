"""The diagnostic verifier must reject substituted sources and incomplete logs."""
import io
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'conformance'))
import legacy_compare_report as report


def fixture_files(original):
    checks, files = {}, {}
    for name, source in {**report.CASES, **report.INVALID}.items():
        failed = original and name in report.EXPECTED_FAILURES
        invalid = name in report.INVALID
        row = {'passed': not failed, 'source': source}
        if not failed:
            row['exit_code'] = 1 if invalid else 0
        checks[name] = row
        suffix = "\nfrom spell.lang.functions import Display\nDisplay('LEGACY_COMPARE_PASSED')\n" if name in report.CASES else ''
        files[name + '/data/Procedures/main.py'] = (source + suffix).encode('utf-8')
        files[name + '/data/Procedures/comparison_fixture.py'] = report.FIXTURE.encode('utf-8')
        files[name + '/native.log'] = b'Error during preparation: Syntax error: invalid syntax' if failed or invalid else b'[ STATUS  ] FINISHED LEGACY_COMPARE_PASSED'
    raw = {'passed': not original, 'controller_exit_code': int(original),
           'checks': checks, 'runtime_sources': {'fixture': 'validator unit test'}}
    return raw, files


def write_archive(tmp_path, raw, files):
    files = {**files, 'checks.json': json.dumps(raw['checks']).encode(),
             'runtime.json': json.dumps(raw['runtime_sources']).encode()}
    with tarfile.open(tmp_path / 'workspace.tar', 'w') as archive:
        for name, data in files.items():
            info = tarfile.TarInfo('./' + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return tmp_path / 'result.json'


@pytest.mark.parametrize('original', [True, False])
def test_complete_differential_archive_is_required(tmp_path, original):
    raw, files = fixture_files(original)
    report.verify_archive(write_archive(tmp_path, raw, files), raw, original)


@pytest.mark.parametrize('mutation', ['missing-check', 'substituted-source', 'modernized-procedure',
    'changed-error-fixture', 'missing-success', 'sanitizer-error', 'missing-syntax-error',
    'hidden-candidate-failure', 'wrong-controller-exit', 'baseline-passes'])
def test_untrustworthy_archive_is_rejected(tmp_path, mutation):
    original = mutation == 'baseline-passes'
    raw, files = fixture_files(original)
    if mutation == 'missing-check':
        del raw['checks']['boundary']
    elif mutation == 'substituted-source':
        raw['checks']['positive']['source'] = 'pass'
    elif mutation == 'modernized-procedure':
        files['positive/data/Procedures/main.py'] = files['positive/data/Procedures/main.py'].replace(b'<>', b'!=')
    elif mutation == 'changed-error-fixture':
        files['failure/data/Procedures/comparison_fixture.py'] = b'pass'
    elif mutation == 'missing-success':
        files['recovery/native.log'] = b'normal exit'
    elif mutation == 'sanitizer-error':
        files['positive/native.log'] += b' AddressSanitizer: heap-use-after-free'
    elif mutation == 'missing-syntax-error':
        files['missing-right-operand/native.log'] = b'other failure'
    elif mutation == 'hidden-candidate-failure':
        raw['checks']['positive']['passed'] = False
    elif mutation == 'wrong-controller-exit':
        raw['controller_exit_code'] = 1
    elif mutation == 'baseline-passes':
        raw['checks']['positive']['passed'] = True
    with pytest.raises(AssertionError):
        report.verify_archive(write_archive(tmp_path, raw, files), raw, original)


@pytest.fixture
def exported(tmp_path):
    sys.path.insert(0, str(report.ROOT / 'source_port'))
    import native_patches
    import dta_time_patches
    digest = lambda value: hashlib.sha256(value).hexdigest()

    def write(name, content):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return digest(content)

    manifest = dict(passed=True, sources={}, recipes={}, artifacts={}, original_artifacts={})
    compiled = dict(passed=True, full_qualification_passed=False, units={}, artifacts={})
    with zipfile.ZipFile(report.ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        for name in report.patch.PREIMAGES:
            original = archive.read(name)
            ported = native_patches.apply(name, original)
            if name.endswith('SPELLpythonHelper.C'):
                ported = dta_time_patches.apply(name, original, ported)
            patched = report.patch.apply(name, original, ported)
            manifest['sources'][name] = {
                label + '_sha256': write(label + '/' + name, content)
                for label, content in (('original', original), ('ported', ported), ('patched', patched))}
            compiled['units'][name] = dict(exit_code=0, original_sha256=digest(ported), patched_sha256=digest(patched))
    for name, source in report.RECIPES.items():
        manifest['recipes'][name] = write(name, (report.ROOT / source).read_bytes())
    compiled['recipe_sha256'] = manifest['recipes']['incremental_native.py']
    before, after = {}, {}
    for name in report.ARTIFACTS:
        original = digest(('original test artifact ' + name).encode())
        patched = write('compiled/' + name, ('changed test artifact ' + name).encode())
        manifest['original_artifacts'][name], manifest['artifacts'][name] = original, patched
        before['spell_native/bin/' + name], after['spell_native/bin/' + name] = original, patched
        compiled['artifacts'][name] = dict(exit_code=0, sha256=patched, original_sha256=original)
    manifest['incremental_build_sha256'] = write('compiled/incremental-build.json', json.dumps(compiled).encode())
    baseline = dict(integrated={'fixture': 'validator unit test'}, installed=before, overlay=None)
    candidate = dict(integrated=baseline['integrated'], installed=after, overlay=manifest)
    write('baseline.json', json.dumps({key: baseline[key] for key in ('integrated', 'installed')}).encode())
    write('manifest.json', json.dumps(manifest).encode())
    return tmp_path, baseline, candidate


def test_exact_export_binds_source_recipe_and_all_installed_changes(exported):
    folder, baseline, candidate = exported
    assert report.verify_export(folder, baseline, candidate) == candidate['overlay']


@pytest.mark.parametrize('mutation', ['source', 'recipe', 'artifact', 'compile-record', 'extra-installed', 'wrong-base'])
def test_altered_export_is_rejected(exported, mutation):
    folder, baseline, candidate = exported
    if mutation == 'source':
        (folder / 'patched' / next(iter(report.patch.PREIMAGES))).write_bytes(b'unverified')
    elif mutation == 'recipe':
        (folder / 'legacy_compare_syntax.py').write_bytes(b'unverified')
    elif mutation == 'artifact':
        (folder / 'compiled/libspell_executor313.so').write_bytes(b'unverified')
    elif mutation == 'compile-record':
        (folder / 'compiled/incremental-build.json').write_text('{}')
    elif mutation == 'extra-installed':
        candidate['installed']['spell/undeclared.py'] = 'unverified'
    elif mutation == 'wrong-base':
        baseline['installed']['spell_native/bin/SPELL-Context'] = 'unverified'
    with pytest.raises((AssertionError, ValueError)):
        report.verify_export(folder, baseline, candidate)
