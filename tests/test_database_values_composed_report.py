"""Only current installed-wheel observations qualify the database octal row."""
import json
import io
from pathlib import Path
import shutil
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
from database_values_composed_report import CONTRACT, qualify


@pytest.fixture(scope='module')
def proof():
    record = json.loads((ROOT / 'conformance/evidence/database_values_composed.json').read_bytes())
    return (Path(record['raw']['values']['path']), Path(record['raw']['user']['path']), record['runtime_image'])


def test_composed_proof_qualifies_only_the_p83_database_literal(proof):
    report = qualify(*proof)
    assert report['qualified_contracts'] == [CONTRACT]
    assert {row['dimension'] for row in report['checks'].values()} == {'positive', 'boundary', 'failure', 'recovery'}
    assert report['regressions'] == {'values_and_import': 24, 'user_persistence': 20, 'user_prompts': 2}
    assert 'Python procedure-source octal literals' in report['exclusions']
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['failed', 'missing-regression', 'image', 'overlay', 'payload',
                                     'source', 'stage', 'prompt', 'fixture', 'archive'])
def test_altered_installed_observations_are_rejected(proof, tmp_path, mutation):
    index = 1 if mutation == 'prompt' else 0
    original = proof[index]
    report = json.loads(original.read_bytes())
    shutil.copyfile(original.parent / 'workspace.tar', tmp_path / 'workspace.tar')
    target = tmp_path / 'result.json'
    target.write_text(json.dumps(report), encoding='utf-8')
    args = list(proof)
    args[index] = target
    qualify(*args)
    if mutation == 'failed':
        report['checks']['octal-values']['passed'] = False
    elif mutation == 'missing-regression':
        del report['checks']['regression-ground:recovery']
    elif mutation == 'image':
        report['runtime_image'] = 'sha256:' + '0' * 64
    elif mutation == 'overlay':
        report['runtime_sources']['overlay'] = {'manifest': {'spell/utils/vimport.py': 'unpackaged'}}
    elif mutation == 'payload':
        report['runtime_sources']['installed']['spell/utils/vimport.py'] = '0' * 64
    elif mutation == 'source':
        report['checks']['octal-values']['source'] = 'assert True'
    elif mutation == 'stage':
        stages = report['runtime_sources']['integrated']['manifest']['composition']['python']['stages']
        stages[:] = [row for row in stages if row['recipe'] != 'database_values_patches.py']
    elif mutation == 'prompt':
        report['prompts']['prompt-abort']['files']['existing.IMP'] = 'OVERWRITTEN'
    elif mutation == 'fixture':
        rewritten = io.BytesIO()
        with tarfile.open(tmp_path / 'workspace.tar') as original, tarfile.open(fileobj=rewritten, mode='w') as changed:
            for member in original:
                content = original.extractfile(member).read() if member.isfile() else None
                if member.name.removeprefix('./') == 'octal-values/data/GroundDB/GDB.DB':
                    content = content.replace(b'OCTAL 035', b'OCTAL 29')
                    member.size = len(content)
                changed.addfile(member, io.BytesIO(content) if content is not None else None)
        (tmp_path / 'workspace.tar').write_bytes(rewritten.getvalue())
    else:
        (tmp_path / 'workspace.tar').write_bytes(b'changed archive')
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError, tarfile.ReadError)):
        qualify(*args)
