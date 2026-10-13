"""Reproduce accepted source bytes and reject drift before compiling a runtime."""
import copy
import json
from pathlib import Path
import sys
import shutil
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
import integrated_patches as composition
import native_patches
import patches

ARCHIVE = ROOT/'docs/reference/SPELL2.6.10-src.zip'


def native_tree(root):
    source = root/'source'
    with zipfile.ZipFile(ARCHIVE) as archive:
        archive.extractall(source)
    native_patches.apply_tree(source)
    return source


def python_tree(root):
    site = root/'site'
    with zipfile.ZipFile(ARCHIVE) as archive:
        for name in composition.PYTHON_NAMES:
            target = site/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(patches.apply(name, archive.read('src/spell/'+name)))
    return site


def verify_evidence(output, report):
    assert json.loads((output/'manifest.json').read_text()) == report
    for name, row in report['sources'].items():
        for label, expected in row.items():
            assert composition.digest((output/label.removesuffix('_sha256')/name).read_bytes()) == expected
    for name, row in report['recipes'].items():
        assert composition.digest((output/'recipes'/name).read_bytes()) == row['sha256']


def test_complete_native_composition_reproduces_qualified_sources(tmp_path):
    source = native_tree(tmp_path)
    report = composition.apply_native_tree(source, ARCHIVE, tmp_path/'evidence')
    qualified = json.loads((ROOT/'distribution/evidence/next-qualified-sources.json').read_bytes())
    expected_sources = qualified['native']
    assert set(expected_sources) == set(composition.NATIVE_NAMES)
    for name, row in expected_sources.items():
        assert report['sources'][name]['patched_sha256'] == row['patched']
        assert composition.digest((source/name).read_bytes()) == row['patched']
    checkpoint = report['checkpoint']
    assert checkpoint['central_identity'] != checkpoint['integrated_identity']
    assert checkpoint['integrated_identity'] in (source/composition.IDENTITY_HEADER).read_text()
    verify_evidence(tmp_path/'evidence', report)


def test_each_composed_recipe_binds_checkpoint_identity():
    recipes = composition.recipe_hashes()
    identity = composition.checkpoint_identity('base', recipes)
    for name in recipes:
        changed = copy.deepcopy(recipes)
        changed[name]['lf_sha256'] = '0'*64
        assert composition.checkpoint_identity('base', changed) != identity, name
    assert composition.checkpoint_identity('other-base', recipes) != identity
    assert composition.checkpoint_identity('base', dict(reversed(list(recipes.items())))) == identity
    for row in recipes.values():
        row['sha256'] = 'raw-line-ending-only-change'
    assert composition.checkpoint_identity('base', recipes) == identity


def test_native_preimage_failure_preserves_tree_then_recovers(tmp_path):
    source = native_tree(tmp_path)
    name = next(iter(composition.flow_patches.PREIMAGES))
    target = source/name
    original = target.read_bytes()
    target.write_bytes(original+b'\n// unqualified drift\n')
    before = {n:(source/n).read_bytes() for n in (*composition.NATIVE_NAMES, composition.IDENTITY_HEADER)}
    with pytest.raises((AssertionError, ValueError)):
        composition.apply_native_tree(source, ARCHIVE, tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    assert before == {n:(source/n).read_bytes() for n in before}
    target.write_bytes(original)
    composition.apply_native_tree(source, ARCHIVE, tmp_path/'recovered')


def test_complete_python_composition_reproduces_qualified_sources(tmp_path):
    site = python_tree(tmp_path)
    report = composition.apply_python_tree(site, ARCHIVE, tmp_path/'evidence')
    expected_sources = json.loads((ROOT/'distribution/evidence/next-qualified-sources.json').read_bytes())['python']
    assert set(expected_sources) == set(composition.PYTHON_NAMES)
    for name in composition.PYTHON_NAMES:
        expected = expected_sources[name]
        assert report['sources'][name]['patched_sha256'] == expected
        assert composition.digest((site/name).read_bytes()) == expected
    verify_evidence(tmp_path/'evidence', report)
    state = {name: row['ported_sha256'] for name,row in report['sources'].items()}
    for stage in report['stages']:
        for name, row in stage['sources'].items():
            assert state[name] == row['before_sha256']
            state[name] = row['after_sha256']
    assert state == {name: row['patched_sha256'] for name,row in report['sources'].items()}


@pytest.mark.parametrize('name', ['spell/lang/helpers/basehelper.py','spell/lib/adapter/config.py'])
def test_python_preimage_failure_preserves_tree_then_recovers(tmp_path, name):
    site = python_tree(tmp_path)
    target = site/name
    original = target.read_bytes()
    target.write_bytes(original+b'\n# unqualified drift\n')
    before = {n:(site/n).read_bytes() for n in composition.PYTHON_NAMES}
    with pytest.raises((AssertionError, ValueError)):
        composition.apply_python_tree(site, ARCHIVE, tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    assert before == {n:(site/n).read_bytes() for n in before}
    target.write_bytes(original)
    composition.apply_python_tree(site, ARCHIVE, tmp_path/'recovered')


def test_changed_original_archive_is_rejected(tmp_path):
    altered = tmp_path/'altered.zip'
    altered.write_bytes(ARCHIVE.read_bytes()+b'drift')
    with pytest.raises(ValueError, match='Unexpected original SPELL'):
        composition.archive_sources(altered, composition.NATIVE_NAMES)


def test_driver_corrections_match_native_evidence_and_preserve_repository(tmp_path):
    source = tmp_path/'src'
    shutil.copytree(ROOT/'driver_plugin/src',source,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    originals = {name:(ROOT/'driver_plugin/src'/name).read_bytes() for name in composition.DRIVER_NAMES}
    report = composition.apply_driver_tree(source, source/'openbexi_dss_proxy/_composition')
    qualified = json.loads((ROOT/'distribution/evidence/next-qualified-sources.json').read_bytes())['driver']
    assert set(qualified) == set(composition.DRIVER_NAMES)
    for name in composition.DRIVER_NAMES:
        assert report['sources'][name]['patched_sha256'] == qualified[name]
        assert (ROOT/'driver_plugin/src'/name).read_bytes() == originals[name]
    assert report['python_sources']['openbexi_dss_proxy/limit_support.py'] == '2f338cf44416dfa042c6f95db5e237e978ff14c345d3cca69e1231ab9ad831ac'
    verify_evidence(source/'openbexi_dss_proxy/_composition', report)


@pytest.mark.parametrize('name', ['openbexi_dss_proxy/tm.py','openbexi_dss_proxy/tc.py'])
def test_driver_preimage_failure_preserves_tree_then_recovers(tmp_path, name):
    source = tmp_path/'src'
    shutil.copytree(ROOT/'driver_plugin/src',source,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    original = (source/name).read_bytes()
    (source/name).write_bytes(original+b'\n# drift\n')
    before = {name:(source/name).read_bytes() for name in composition.DRIVER_NAMES}
    with pytest.raises(ValueError):
        composition.apply_driver_tree(source, tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    assert before == {name:(source/name).read_bytes() for name in before}
    (source/name).write_bytes(original)
    composition.apply_driver_tree(source, tmp_path/'recovered')
