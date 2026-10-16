"""The diagnostic verifier must reject substituted sources and incomplete logs."""
import io
import json
from pathlib import Path
import sys
import tarfile

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
        files[name + '/native.log'] = b'SyntaxError' if failed or invalid else b'[ STATUS  ] FINISHED LEGACY_COMPARE_PASSED'
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
