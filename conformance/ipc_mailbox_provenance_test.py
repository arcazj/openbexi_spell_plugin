"""Reject diagnostic records that hide changed binaries or missing controls."""
import copy
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'conformance'))
import checkpoint_identity_provenance_test as identity_fixtures
from ipc_mailbox_provenance import RECIPES, qualification_identity


@pytest.fixture
def evidence():
    fixture = identity_fixtures.IdentityTests()
    fixture.setUp()
    base = fixture.record
    inputs = dict(fixture.inputs)
    inputs.update({path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                   for path in RECIPES.values()})
    names = ('libspell_executor313.so', 'SPELL-Context', 'SPELL-Listener')
    overlay = dict(passed=True, full_release_accepted=False,
        artifacts={name: 'changed-' + name for name in names},
        original_artifacts={name: base['native_artifacts'][name] for name in names},
        recipes={name: inputs[path] for name, path in RECIPES.items()},
        probes={label + '-' + operation: dict(exit_code=1 if label == 'original' else 0)
                for label in ('original', 'patched') for operation in ('place', 'cancel')})
    return dict(baseline=base, mailbox_overlay=overlay,
                host_native_sha256=base['host_native_sha256']), inputs


def test_declared_overlay_is_not_distribution_acceptance(evidence):
    record, inputs = evidence
    identity = qualification_identity(record, inputs)
    assert identity['kind'] == 'diagnostic-mailbox-overlay'
    assert identity['native_artifacts'] == record['mailbox_overlay']['artifacts']
    assert identity['baseline']['kind'] == 'installed-composition'


@pytest.mark.parametrize('mutation', ['missing-artifact', 'extra-artifact', 'wrong-base',
    'unchanged-artifact', 'recipe', 'missing-probe', 'baseline-passes', 'fixed-fails',
    'release-claim', 'host-source', 'checkpoint-source'])
def test_invalid_or_incomplete_evidence_is_rejected(evidence, mutation):
    record, inputs = copy.deepcopy(evidence)
    overlay = record['mailbox_overlay']
    library = 'libspell_executor313.so'
    if mutation == 'missing-artifact':
        del overlay['artifacts']['SPELL-Listener']
    elif mutation == 'extra-artifact':
        overlay['artifacts']['unrelated'] = 'changed'
    elif mutation == 'wrong-base':
        overlay['original_artifacts'][library] = 'unverified'
    elif mutation == 'unchanged-artifact':
        overlay['artifacts'][library] = overlay['original_artifacts'][library]
    elif mutation == 'recipe':
        overlay['recipes']['ipc_mailbox_patches.py'] = 'different-recipe'
    elif mutation == 'missing-probe':
        del overlay['probes']['original-cancel']
    elif mutation == 'baseline-passes':
        overlay['probes']['original-place']['exit_code'] = 0
    elif mutation == 'fixed-fails':
        overlay['probes']['patched-cancel']['exit_code'] = 1
    elif mutation == 'release-claim':
        overlay['full_release_accepted'] = True
    elif mutation == 'host-source':
        record['host_native_sha256'] = 'different-host'
    elif mutation == 'checkpoint-source':
        record['baseline']['manifest']['composition']['native']['sources'].clear()
    with pytest.raises(ValueError):
        qualification_identity(record, inputs)
