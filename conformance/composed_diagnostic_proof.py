"""Require fresh native stages to reproduce a committed diagnostic correction."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DONORS = {
    'wait_interrupt': ('728d9ba4fc154f7bbb924233d3b67e8fa7043de0', 24, 1),
    'proc_dictionary': ('c22ba3d0f5e2362c2384f09036bfff30e83080b1', 16, 2),
}


def verify_donor(runtime, kind):
    commit, count, units = DONORS[kind]
    path = 'conformance/evidence/' + kind + '.json'
    encoded = subprocess.check_output(['git', 'show', commit + ':' + path], cwd=ROOT)
    donor = json.loads(encoded)
    assert donor['passed'] is True and donor['qualified_contracts'] == []
    assert len(donor['checks']) == count + 4
    assert all(row['passed'] is True for row in donor['checks'].values())
    overlay = donor['qualification_identity']['evidence']
    assert overlay['passed'] is True and not overlay['full_release_accepted']
    native = runtime['manifest']['composition']['native']
    recipe = kind + '_patches.py'
    stages = [row for row in native['stages'] if row['recipe'] == recipe]
    assert len(stages) == units
    changed = {}
    for stage in stages:
        assert not set(changed) & set(stage['sources'])
        changed.update(stage['sources'])
    assert set(changed) == set(overlay['sources']) and len(changed) == units
    committed = subprocess.check_output(['git', 'show', commit + ':source_port/' + recipe], cwd=ROOT)
    assert hashlib.sha256(committed).hexdigest() == overlay['recipes'][recipe]
    assert native['recipes'][recipe]['sha256'] == overlay['recipes'][recipe]
    for name, row in overlay['sources'].items():
        assert changed[name] == dict(before_sha256=row['ported_sha256'], after_sha256=row['patched_sha256'])
        assert native['sources'][name]['original_sha256'] == row['original_sha256']
        assert native['sources'][name]['patched_sha256'] == row['patched_sha256']
    return dict(commit=commit, path=path, sha256=hashlib.sha256(encoded).hexdigest(), stages=stages)
