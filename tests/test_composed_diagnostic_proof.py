"""Source provenance rejects altered stages even when all native checks say pass."""
from copy import deepcopy
from pathlib import Path
import sys
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'source_port'),str(ROOT/'conformance')]
import native_patches
import integrated_patches
from composed_diagnostic_proof import verify_donor


@pytest.fixture(scope='module')
def composed(tmp_path_factory):
    root=tmp_path_factory.mktemp('diagnostic-composition')
    source=root/'source';archive=ROOT/'docs/reference/SPELL2.6.10-src.zip'
    with zipfile.ZipFile(archive) as bundle:bundle.extractall(source)
    native_patches.apply_tree(source)
    native=integrated_patches.apply_native_tree(source,archive,root/'evidence')
    return dict(manifest=dict(composition=dict(native=native)))


@pytest.mark.parametrize('kind',['wait_interrupt','proc_dictionary'])
def test_composition_reproduces_exact_committed_donor(composed,kind):
    proof=verify_donor(composed,kind)
    assert len(proof['commit'])==40 and len(proof['sha256'])==64


@pytest.mark.parametrize('kind',['wait_interrupt','proc_dictionary'])
@pytest.mark.parametrize('change',['recipe','missing-stage','duplicate-stage','predecessor','output','original'])
def test_changed_donor_chain_is_rejected(composed,kind,change):
    runtime=deepcopy(composed);native=runtime['manifest']['composition']['native']
    recipe=kind+'_patches.py';stage=next(s for s in native['stages'] if s['recipe']==recipe)
    name=next(iter(stage['sources']))
    if change=='recipe':native['recipes'][recipe]['sha256']='0'*64
    elif change=='missing-stage':native['stages'].remove(stage)
    elif change=='duplicate-stage':native['stages'].append(deepcopy(stage))
    elif change=='predecessor':stage['sources'][name]['before_sha256']='0'*64
    elif change=='output':native['sources'][name]['patched_sha256']='0'*64
    else:native['sources'][name]['original_sha256']='0'*64
    with pytest.raises(AssertionError):verify_donor(runtime,kind)
