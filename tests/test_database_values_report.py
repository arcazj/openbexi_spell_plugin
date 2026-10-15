"""The diagnostic overlay must retain its source and native persistence evidence."""
import json
from pathlib import Path
import shutil
import hashlib
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
import database_values_report as diagnostic
from database_values_report import qualify


@pytest.fixture(scope='module')
def proof(tmp_path_factory):
    record = json.loads((ROOT / 'conformance/evidence/database_values.json').read_bytes())
    # This diagnostic predates the composed package. Verify it against its exact
    # committed inputs; current-runtime acceptance has a separate test module.
    frozen = tmp_path_factory.mktemp('octal-diagnostic-donor')
    donor = 'a494986733ce6f4ceefda41684824f12bfbc5660'
    names = dict(record['inputs'])
    names.update({'conformance/evidence/' + name + '.json': row['sha256']
                  for name, row in record['retained_failures'].items()})
    for name, expected in names.items():
        current = (ROOT / name).read_bytes()
        contents = current if hashlib.sha256(current).hexdigest() == expected else subprocess.check_output(
            ['git', 'show', donor + ':' + name], cwd=ROOT)
        assert hashlib.sha256(contents).hexdigest() == expected, name
        target = frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    original_validate = diagnostic.validate_report
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(diagnostic, 'ROOT', frozen)
        patch.setattr(diagnostic, 'validate_report',
            lambda path, image, count: original_validate(path, image, count, root=frozen))
        yield (Path(record['raw']['values']['path']), Path(record['raw']['user']['path']),
               Path(record['build']['path']))


def test_diagnostic_pass_does_not_promote_an_overlaid_artifact(proof):
    report = qualify(*proof)
    assert report['passed_checks'] == {'values_and_import': 24, 'user_persistence': 20, 'user_prompts': 2}
    assert report['qualified_contracts'] == []
    assert report['source']['name'] == 'spell/utils/vimport.py'
    assert not report['full_v05_accepted'] and not report['full_v06_accepted']


@pytest.mark.parametrize('mutation', ['failed', 'missing-regression', 'image', 'recipe', 'payload', 'prompt'])
def test_altered_diagnostic_observations_are_rejected(proof, tmp_path, mutation):
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
        report['runtime_image'] = report['runtime_sources']['profile']
    elif mutation == 'recipe':
        report['runtime_sources']['overlay']['files']['database_values_patches.py'] = '0' * 64
    elif mutation == 'payload':
        report['runtime_sources']['installed']['spell/utils/vimport.py'] = '0' * 64
    else:
        report['prompts']['prompt-abort']['files']['existing.IMP'] = 'OVERWRITTEN'
    target.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises((AssertionError, ValueError)):
        qualify(*args)
