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
    qualified = json.loads((ROOT/'distribution/evidence/followup-qualified-sources.json').read_bytes())
    expected_sources = qualified['native']
    for name,digest in qualified['native_distribution'].items():
        assert composition.digest((ROOT/name).read_bytes()) == digest
    assert set(expected_sources) == set(composition.NATIVE_NAMES)
    for name, row in expected_sources.items():
        assert report['sources'][name] == {label+'_sha256':value for label,value in row.items()}
        assert composition.digest((source/name).read_bytes()) == row['patched']
    checkpoint = report['checkpoint']
    assert checkpoint['central_identity'] != checkpoint['integrated_identity']
    assert checkpoint['integrated_identity'] in (source/composition.IDENTITY_HEADER).read_text()
    state = {name: row['ported_sha256'] for name,row in report['sources'].items()}
    for stage in report['stages']:
        assert stage['recipe'] in report['recipes']
        for name,row in stage['sources'].items():
            assert state[name] == row['before_sha256']
            state[name] = row['after_sha256']
    assert state == {name: row['patched_sha256'] for name,row in report['sources'].items()}
    context_stages = [row for row in report['stages'] if composition.checkpoint_context_patches.SOURCE in row['sources']]
    assert [row['recipe'] for row in context_stages] == ['data_files_native_patches.py','checkpoint_context_patches.py']
    child_context_stages = [row for row in report['stages'] if composition.shutdown_pause_patches.SOURCE in row['sources']]
    assert [row['recipe'] for row in child_context_stages] == ['shutdown_pause_patches.py','child_lifecycle_patches.py']
    helper = 'lib/SPELL_UTIL/src/SPELLpythonHelper.C'
    assert [row['recipe'] for row in report['stages'] if helper in row['sources']] == [
        'dta_time_patches.py', 'legacy_compare_patches.py']
    listener = composition.context_snapshot_patches.SOURCE
    assert [row['recipe'] for row in report['stages'] if listener in row['sources']] == [
        'context_snapshot_patches.py']
    prompt = composition.prompt_startup_patches.SOURCE
    assert [row['recipe'] for row in report['stages'] if prompt in row['sources']] == [
        'child_lifecycle_patches.py', 'prompt_timeout_patches.py',
        'prompt_control_patches.py', 'prompt_startup_patches.py', 'prompt_complete_patches.py']
    verify_evidence(tmp_path/'evidence', report)

    scheduler = composition.wait_interrupt_patches.SOURCE
    assert [row['recipe'] for row in report['stages'] if scheduler in row['sources']] == [
        'scheduler_patches.py', 'wait_interrupt_patches.py']
    for name in composition.proc_dictionary_patches.PREIMAGES:
        assert [row['recipe'] for row in report['stages'] if name in row['sources']] == [
            'proc_dictionary_patches.py']


def test_host_inputs_match_their_separate_qualified_donors():
    qualified = json.loads((ROOT/'distribution/evidence/followup-qualified-sources.json').read_bytes())
    for group in ('host', 'host_client', 'host_package'):
        assert qualified[group]
        for name, expected in qualified[group].items():
            assert composition.digest((ROOT/name).read_bytes()) == expected, name


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


@pytest.mark.parametrize('name', [next(iter(composition.flow_patches.PREIMAGES)),
                                 composition.checkpoint_error_patches.SOURCE,
                                 composition.checkpoint_identity_patches.SOURCE,
                                 *composition.child_lifecycle_patches.PREIMAGES,
                                 *composition.prompt_timeout_patches.PREIMAGES,
                                 *composition.prompt_control_patches.PREIMAGES,
                                 composition.prompt_complete_patches.HEADER,
                                 composition.ipc_mailbox_patches.SOURCE,
                                 composition.context_snapshot_patches.SOURCE,
                                 *composition.legacy_compare_patches.PREIMAGES,
                                 *composition.proc_dictionary_patches.PREIMAGES,
                                 composition.wait_interrupt_patches.SOURCE,
                                 composition.checkpoint_context_patches.SOURCE])
def test_native_preimage_failure_preserves_tree_then_recovers(tmp_path, name):
    source = native_tree(tmp_path)
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


def test_child_shutdown_union_preserves_donor_and_rejects_drift(tmp_path, monkeypatch):
    source = native_tree(tmp_path)
    recipe = composition.shutdown_pause_patches
    name = recipe.SOURCE
    original = composition.archive_sources(ARCHIVE,[name])[name]
    ported = (source/name).read_bytes()
    shutdown = recipe.apply(name,original,ported)
    child = composition.child_lifecycle_patches.apply(name,original,ported)
    combined = composition.compose_child_shutdown(name,original,ported,shutdown)
    assert combined.replace(recipe.AFTER.encode(),recipe.BEFORE.encode()) == child
    with pytest.raises(ValueError,match='exact shutdown output'):
        composition.compose_child_shutdown(name,original,ported,shutdown+b'\n')
    monkeypatch.setattr(composition.child_lifecycle_patches,'apply',
        lambda *_:child.replace(recipe.BEFORE.encode(),b'overlapping edit'))
    with pytest.raises(ValueError,match='overlaps'):
        composition.compose_child_shutdown(name,original,ported,shutdown)


def test_context_recovery_recipe_rejects_execution_before_data_stage(tmp_path):
    source = native_tree(tmp_path)
    name = composition.checkpoint_context_patches.SOURCE
    original = composition.archive_sources(ARCHIVE,[name])[name]
    ported = (source/name).read_bytes()
    with pytest.raises(ValueError,match='composed context'):
        composition.checkpoint_context_patches.apply(name,original,ported)
    assert (source/name).read_bytes() == ported
    data = composition.data_files_native_patches.apply(original,ported)
    assert composition.digest(data) == composition.checkpoint_context_patches.PORTED
    assert composition.checkpoint_context_patches.apply(name,original,data) != data


def test_complete_python_composition_reproduces_qualified_sources(tmp_path):
    site = python_tree(tmp_path)
    report = composition.apply_python_tree(site, ARCHIVE, tmp_path/'evidence')
    expected_sources = json.loads((ROOT/'distribution/evidence/followup-qualified-sources.json').read_bytes())['python']
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


def test_legacy_comparison_requires_qualified_time_output(tmp_path):
    source = native_tree(tmp_path)
    name = 'lib/SPELL_UTIL/src/SPELLpythonHelper.C'
    original = composition.archive_sources(ARCHIVE, [name])[name]
    ported = (source / name).read_bytes()
    with pytest.raises(ValueError, match='Legacy comparison preimage differs'):
        composition.legacy_compare_patches.apply(name, original, ported)
    timed = composition.dta_time_patches.apply(name, original, ported)
    assert composition.legacy_compare_patches.apply(name, original, timed) != timed


def test_octal_recipe_cannot_precede_user_database_stage(tmp_path, monkeypatch):
    site = python_tree(tmp_path)
    before = {name:(site/name).read_bytes() for name in composition.PYTHON_NAMES}
    recipes = list(composition.PYTHON_RECIPES)
    recipes.remove(composition.database_values_patches)
    recipes.insert(recipes.index(composition.user_database_patches), composition.database_values_patches)
    monkeypatch.setattr(composition, 'PYTHON_RECIPES', tuple(recipes))
    with pytest.raises(ValueError, match='Unexpected composed database value importer'):
        composition.apply_python_tree(site, ARCHIVE, tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    assert before == {name:(site/name).read_bytes() for name in before}


def test_send_recipe_cannot_precede_required_timing_stage(tmp_path, monkeypatch):
    site = python_tree(tmp_path)
    before = {name:(site/name).read_bytes() for name in composition.PYTHON_NAMES}
    recipes = list(composition.PYTHON_RECIPES)
    recipes.remove(composition.send_verify_patches)
    recipes.insert(recipes.index(composition.timing_patches), composition.send_verify_patches)
    monkeypatch.setattr(composition, 'PYTHON_RECIPES', tuple(recipes))
    with pytest.raises(AssertionError, match='spell/lang/helpers/tchelper.py'):
        composition.apply_python_tree(site, ARCHIVE, tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    assert before == {name:(site/name).read_bytes() for name in before}


@pytest.mark.parametrize('name', ['spell/lang/helpers/basehelper.py','spell/lib/adapter/config.py',
                                 'spell/lang/helpers/rnghelper.py', 'spell/utils/vimport.py'])
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
    expected = json.loads((ROOT/'distribution/evidence/followup-qualified-sources.json').read_bytes())
    qualified = expected['driver']
    for name,digest in expected['driver_additions'].items():
        assert report['python_sources'][name]==digest
    assert set(qualified) == set(composition.DRIVER_NAMES)
    for name in composition.DRIVER_NAMES:
        assert report['sources'][name]['patched_sha256'] == qualified[name]
        assert (ROOT/'driver_plugin/src'/name).read_bytes() == originals[name]
    assert report['python_sources']['openbexi_dss_proxy/limit_support.py'] == '2f338cf44416dfa042c6f95db5e237e978ff14c345d3cca69e1231ab9ad831ac'
    verify_evidence(source/'openbexi_dss_proxy/_composition', report)


@pytest.mark.parametrize('name', ['openbexi_dss_proxy/tm.py','openbexi_dss_proxy/tc.py',
                                 'openbexi_dss_proxy/ranging.py','openbexi_spell_dss/ground.py'])
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
