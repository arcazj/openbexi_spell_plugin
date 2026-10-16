"""Retained native database evidence rejects rebinding and forged outcomes."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tarfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import database_format_review as review


@pytest.fixture(scope='module')
def retained():
    proof=review.read(ROOT/'conformance/evidence/database_format_review.json')
    result={}
    for key,row in proof['raw'].items():
        path=Path(row['path']);assert review.sha(path)==row['sha256']
        with tarfile.open(path.parent/'workspace.tar') as archive:
            files={v.name.removeprefix('./'):archive.extractfile(v).read() for v in archive.getmembers() if v.isfile()}
        result[key]=(review.read(path),files)
    return proof,result


def test_all_52_native_cases_and_prompt_files_are_independently_reviewed(retained):
    proof,_=retained
    paths={k:Path(v['path']) for k,v in proof['raw'].items()}
    actual=review.review(paths,Path(proof['overlay']),Path(proof['telemetry_overlay']),Path(proof['limit_overlay']),
                         proof['source_revision'],proof['runtime_image'])
    assert json.dumps(actual['checks'],sort_keys=True)==json.dumps(proof['checks'],sort_keys=True)
    assert len(actual['checks'])==52 and not actual['qualified_contracts']


@pytest.mark.parametrize('mutation',['key-type','time-precision','literal-time','failed-save-file','recovery-file',
    'unsafe-expression','procedure','numeric-pass','sanitizer','prompt-file','prompt-status'])
def test_forged_files_and_rebound_reports_are_rejected(retained,mutation):
    proof,items=retained
    suite='user' if mutation.startswith('prompt-') else 'formats'
    raw,files=deepcopy(items[suite])
    target=lambda n:n+'/data/User/MyData/data.IMP'
    if mutation=='key-type':files[target('keys-positive')]=files[target('keys-positive')].replace(b'42\t',b"'42'\t")
    elif mutation=='time-precision':files[target('nested-time-positive')]=files[target('nested-time-positive')].replace(b'.123456',b'.123457')
    elif mutation=='literal-time':files[target('nested-time-boundary')]=files[target('nested-time-boundary')].replace(b'not a timestamp',b'not a timestamp!')
    elif mutation=='failed-save-file':files[target('keys-failure')]=b'KEY\t99\n'
    elif mutation=='recovery-file':files[target('keys-recovery')]=b'KEY\t42\n'
    elif mutation=='unsafe-expression':files[target('nested-time-positive')]=b"VALUES\t__import__('os').getcwd()\n"
    elif mutation=='procedure':files['keys-positive/data/Procedures/main.py']=b'pass\n'
    elif mutation=='numeric-pass':
        raw['checks']['keys-positive']['passed']=1;files['checks.json']=json.dumps(raw['checks']).encode()
    elif mutation=='sanitizer':files['keys-positive/native.log']+=b'AddressSanitizer: error\n'
    elif mutation=='prompt-file':files['prompt-rename/database-files/existing.IMP']=b'overwritten\n'
    else:
        raw['prompts']['prompt-abort']['status']='FINISHED';files['prompts.json']=json.dumps(raw['prompts']).encode()
    with pytest.raises(AssertionError):review.archive_proof(raw,files,proof['source_revision'])
