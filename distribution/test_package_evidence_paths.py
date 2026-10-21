"""An evidence path may be relative to its report and must retain its exact hash."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('changed',[False,True])
def test_report_relative_capture_is_verified_before_adoption(tmp_path,changed):
    reports=tmp_path/'.qualification/verifier'
    verdict=reports/'reports/product/verification-verdict.txt'
    verdict.parent.mkdir(parents=True)
    verdict.write_bytes(b'Compatible\n')
    expected=hashlib.sha256(verdict.read_bytes()).hexdigest()
    if changed:verdict.write_bytes(b'Altered verdict\n')
    seed=reports/'result.json'
    seed.write_text(json.dumps(dict(verdict=dict(path='reports/product/verification-verdict.txt',
                                               sha256=expected))),encoding='utf-8')
    output=tmp_path/'audit'
    result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'distribution/package_evidence.py'),
        '--seed',str(seed),'--output',str(output),'--audit-only'],capture_output=True,cwd=ROOT)
    audit=json.loads((output/'result.json').read_bytes())
    assert result.returncode==int(changed)
    assert audit['passed'] is (not changed)
    if not changed:
        manifest=json.loads((output/'MANIFEST.json').read_bytes())
        assert any(row['path']==str(verdict.resolve()) and row['sha256']==expected
                   for row in manifest['files'].values())
    else:assert audit['issues'][0]['expected']==expected
