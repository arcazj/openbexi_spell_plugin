"""Historical input validation stays pinned while current files are always re-read."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from evidence_sources import source_bytes
from run_language_regressions import validate_report


def test_current_and_immutable_historical_sources_are_checked_independently(tmp_path):
    def git(*args):
        return subprocess.check_output(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',*args],cwd=tmp_path)
    git('init','--quiet')
    path=tmp_path/'oracle.py';path.write_bytes(b'original\n')
    git('add','oracle.py');git('commit','--quiet','-m','Freeze fixture')
    commit=git('rev-parse','HEAD').decode().strip()
    report=tmp_path/'result.json'
    report.write_text(json.dumps(dict(runtime_image='candidate',checks=dict(one=dict(passed=True)),
        inputs={'oracle.py':hashlib.sha256(path.read_bytes()).hexdigest()})))
    validate_report(report,'candidate',1,tmp_path,source_revision=commit)
    path.write_bytes(b'changed\n')
    assert source_bytes(tmp_path,'oracle.py',commit)==b'original\n'
    with pytest.raises(ValueError,match='source changed'):validate_report(report,'candidate',1,tmp_path)
    validate_report(report,'candidate',1,tmp_path,source_revision=commit)
    path.unlink()
    with pytest.raises(FileNotFoundError):source_bytes(tmp_path,'oracle.py')
    assert source_bytes(tmp_path,'oracle.py',commit)==b'original\n'


@pytest.mark.parametrize('revision',['HEAD','master','1234567','-not-a-commit'])
def test_mutable_or_partial_revision_rejected(tmp_path,revision):
    with pytest.raises(ValueError,match='immutable'):source_bytes(tmp_path,'file.py',revision)


@pytest.mark.parametrize('revision',[None,'0'*40])
def test_input_cannot_escape_repository(tmp_path,revision):
    with pytest.raises(ValueError,match='escapes'):source_bytes(tmp_path,'../outside.py',revision)
