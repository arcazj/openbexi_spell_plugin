"""Prevent successful process exits from hiding failed qualification evidence."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_language_regressions import report_from_stdout, validate_report


@pytest.fixture
def raw(tmp_path):
    source = tmp_path / 'oracle.py'
    source.write_bytes(b'original oracle\n')
    payload = {'runtime_image': 'sha256:candidate',
               'checks': {'case': {'passed': True}},
               'inputs': {'oracle.py': hashlib.sha256(source.read_bytes()).hexdigest()}}
    return tmp_path, payload


@pytest.mark.parametrize('defect', ['failed-check', 'empty-checks', 'failed-controller',
                                  'failed-summary', 'wrong-image', 'changed-source', 'missing-inputs'])
def test_invalid_report_rejected_even_with_successful_process_exit(raw, defect):
    root, payload = raw
    if defect == 'failed-check':
        payload['checks']['case']['passed'] = False
    elif defect == 'empty-checks':
        payload['checks'] = {}
    elif defect == 'failed-controller':
        payload['controller_exit_code'] = 1
    elif defect == 'failed-summary':
        payload['passed'] = False
    elif defect == 'wrong-image':
        payload['runtime_image'] = 'sha256:historical'
    elif defect == 'changed-source':
        (root / 'oracle.py').write_bytes(b'revised oracle\n')
    elif defect == 'missing-inputs':
        payload['inputs'] = {}
    path = root / 'result.json'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        validate_report(path, 'sha256:candidate', 1, root)


def test_valid_report_records_exact_file_identity(raw):
    root, payload = raw
    path = root / 'result.json'
    path.write_text(json.dumps(payload))
    observed = validate_report(path, 'sha256:candidate', 1, root)
    assert observed['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert observed['source_inputs_verified'] == 1


def test_runner_summary_after_diagnostic_output():
    assert report_from_stdout('diagnostic {text}\n' + json.dumps(
        {'evidence': 'retained-run', 'checks': 24})) == Path('retained-run/result.json')
    with pytest.raises(ValueError):
        report_from_stdout('{"passed": true}')
