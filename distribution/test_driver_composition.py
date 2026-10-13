"""Check driver composition/RECORD binding without starting external services."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
sys.path.insert(0, str(ROOT/'driver_plugin/src'))
from integrated_patches import apply_driver_tree, recipe_hashes
from openbexi_dss_proxy.provenance import PREFIX, verify


def tree(tmp_path):
    site = tmp_path/'src'
    shutil.copytree(ROOT/'driver_plugin/src', site, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    apply_driver_tree(site, site/PREFIX)
    return site


def test_complete_driver_provenance_verifies(tmp_path):
    site = tree(tmp_path)
    record = verify(lambda name: (site/name).read_bytes(), recipe_hashes())
    assert record['profile'] == 'repository-dss-integrated-wheel/1'
    assert 'openbexi_dss_proxy/limit_support.py' in record['manifest']['python_sources']
    assert 'openbexi_dss_proxy/provenance.py' in record['manifest']['python_sources']


@pytest.mark.parametrize('name', [
    'openbexi_dss_proxy/tm.py', 'openbexi_dss_proxy/limit_support.py',
    PREFIX+'original/openbexi_dss_proxy/tm.py', PREFIX+'recipes/limit_patches.py'])
def test_driver_correction_and_unchanged_support_drift_are_rejected(tmp_path, name):
    site = tree(tmp_path)
    path = site/name
    original = path.read_bytes()
    path.write_bytes(original+b'\n# unqualified drift\n')
    with pytest.raises(ValueError, match='differs'):
        verify(lambda name: (site/name).read_bytes(), recipe_hashes())
    path.write_bytes(original)
    verify(lambda name: (site/name).read_bytes(), recipe_hashes())


def test_driver_manifest_cannot_skip_correction_chain_or_change_native_recipes(tmp_path):
    site = tree(tmp_path)
    target = site/PREFIX/'manifest.json'
    original = target.read_bytes()
    manifest = json.loads(original)
    manifest['stages'] = []
    target.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='composition output differs'):
        verify(lambda name: (site/name).read_bytes(), recipe_hashes())
    target.write_bytes(original)
    other = recipe_hashes()
    other['limit_patches.py']['sha256'] = '0'*64
    with pytest.raises(ValueError, match='native composition recipes differ'):
        verify(lambda name: (site/name).read_bytes(), other)
