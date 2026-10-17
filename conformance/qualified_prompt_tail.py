"""Preserve earlier prompt proofs while checking the reviewed final source tail."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def extend(native, name, before):
    recipe = 'prompt_complete_patches.py'
    if recipe not in native['recipes']:
        return before
    stages = [stage['sources'][name] for stage in native['stages']
              if stage['recipe'] == recipe and name in stage['sources']]
    if not stages:
        return before
    # The generator pins this independently reviewed source donor to a commit;
    # current implementation bytes alone never define an accepted expectation.
    qualified = json.loads((ROOT/'distribution/evidence/followup-qualified-sources.json').read_bytes())
    donor = qualified['donors']['prompt_complete']
    encoded = subprocess.check_output(['git', 'show', donor['commit']+':'+donor['path']], cwd=ROOT)
    assert hashlib.sha256(encoded).hexdigest() == donor['sha256']
    proof = json.loads(encoded)
    assert proof['passed'] is True
    assert set(proof['independent_reviews']) == {'prompt', 'child', 'event'}
    change = proof['native_changes'][name]
    assert change['before_sha256'] == before
    assert stages == [{key: change[key] for key in ('before_sha256', 'after_sha256')}]
    assert native['sources'][name] == {key+'_sha256': value for key, value in proof['native'][name].items()}
    expected = proof['recipes'][recipe]
    assert hashlib.sha256((ROOT/'source_port'/recipe).read_bytes()).hexdigest() == expected
    assert native['recipes'][recipe]['sha256'] == expected
    return change['after_sha256']
