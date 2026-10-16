"""Draft acceptance/forgery checks for the retained native display diagnostic."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import display_report as report
from check import supported_check


def canonical():
    return json.loads((ROOT/'conformance/evidence/display.json').read_bytes())


def test_accepts_real_display_diagnostic_without_promoting_coverage():
    saved=canonical()
    actual=report.qualify(Path(saved['raw']['path']),Path(saved['baseline']['path']),saved['runtime_image'],
                          Path(saved['overlay_manifest']['path']).parent,saved['baseline_revision'])
    assert actual['passed'] and len(actual['candidate_contracts'])==24
    assert actual['qualified_contracts']==[] and not actual['full_v05_accepted']
    assert len(actual['checks'])==35+24*4
    for contract in actual['candidate_contracts']:
        assert all(actual['checks'][contract+':'+dimension]['contracts']==[contract] for dimension in report.DIMENSIONS)
        assert all(supported_check(actual,contract+':'+dimension,dimension) for dimension in report.DIMENSIONS)


@pytest.mark.parametrize('mutation', ['result','return','dimension','native-byte','extra-source','download','recipe','baseline'])
def test_rejects_forged_display_evidence(tmp_path,mutation):
    saved=canonical();original=Path(saved['raw']['path'])
    raw=deepcopy(json.loads(original.read_bytes()))
    shutil.copytree(original.parent/'workspace',tmp_path/'workspace')
    overlay_original=Path(saved['overlay_manifest']['path']).parent
    overlay=tmp_path/'overlay';shutil.copytree(overlay_original,overlay)
    baseline=Path(saved['baseline']['path'])
    def write(name,value):
        target=tmp_path/'workspace'/name
        target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        raw['artifacts'][name]=hashlib.sha256(target.read_bytes()).hexdigest()
    if mutation=='result':
        raw['passed']=False
    elif mutation=='return':
        raw['checks']['lifecycle:positive']['calls'][0]['returned']=False
        write('procedure/checks.json',raw['checks'])
    elif mutation=='dimension':
        raw['checks']['lifecycle:recovery']['dimension']='positive'
        write('procedure/checks.json',raw['checks'])
    elif mutation in ('native-byte','extra-source'):
        runtime=raw['runtime_sources']
        if mutation=='native-byte':
            name=next(key for key in runtime['installed'] if key.endswith('/libspell_executor313.so'))
            runtime['installed'][name]='0'*64
        else:
            runtime['installed']['spell/undeclared_display_change.py']='0'*64
        write('runtime.json',runtime)
    elif mutation=='download':
        name=next(name for name in raw['artifacts'] if name.startswith('downloads/') and name.endswith('.ps'))
        target=tmp_path/'workspace'/name
        target.write_bytes(b'%!PS-Adobe-3.0\n%%EOF\n')
        raw['artifacts'][name]=hashlib.sha256(target.read_bytes()).hexdigest()
    elif mutation=='recipe':
        target=overlay/'display_patches.py'
        target.write_bytes(target.read_bytes()+b'\n')
    else:
        cloned=tmp_path/'baseline';cloned.mkdir()
        shutil.copytree(baseline.parent/'workspace',cloned/'workspace')
        value=json.loads(baseline.read_bytes())
        value['checks']['api-surface']['observed']['functions']['OpenWorkspace']=True
        baseline=cloned/'result.json';baseline.write_text(json.dumps(value),encoding='utf-8')
    path=tmp_path/'result.json';path.write_text(json.dumps(raw),encoding='utf-8')
    with pytest.raises((AssertionError,ValueError,KeyError)):
        report.qualify(path,baseline,saved['runtime_image'],overlay,saved['baseline_revision'])
