"""Fresh installed packages must reproduce the independently observed behaviors."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'conformance'))
import command_display_composed_report as report
from check import supported_check


def canonical():
    return json.loads((ROOT/'conformance/evidence/command_display_composed.json').read_bytes())


def successor_fixture():
    runtime = canonical()['runtime_sources']['integrated']
    native = deepcopy(runtime['manifest']['composition']['native'])
    driver = deepcopy(runtime['driver_composition']['manifest'])
    expected = json.loads((ROOT/'distribution/evidence/followup-qualified-sources.json').read_bytes())
    return native,driver,expected


def test_v06_successors_retain_frozen_donors_and_exact_final_identities():
    native,driver,expected = successor_fixture()
    before = deepcopy(expected)
    native_sources,driver_sources,corrections = report.review_successors(native,driver,expected)
    assert expected == before
    assert set(corrections) == {'lib/SPELL_EXC/src/SPELLframeManager.C',
                                'openbexi_dss_proxy/command_settings.py'}
    assert all(native['sources'][name] == row for name,row in native_sources.items())
    assert all(driver['python_sources'][name] == digest for name,digest in driver_sources.items())


@pytest.mark.parametrize('mutation', ['native-output','native-original','native-preimage',
    'native-recipe','native-unknown','native-stage','driver-output','driver-original',
    'driver-stage','driver-recipe','driver-unknown','frozen-native','frozen-driver'])
def test_v06_successors_reject_changed_or_unreviewed_source_chains(mutation):
    native,driver,expected = successor_fixture()
    frame = 'lib/SPELL_EXC/src/SPELLframeManager.C'
    settings = 'openbexi_dss_proxy/command_settings.py'
    if mutation == 'native-output':native['sources'][frame]['patched_sha256'] = '0'*64
    elif mutation == 'native-original':native['sources'][frame]['original_sha256'] = '0'*64
    elif mutation == 'native-preimage':native['sources'][frame]['ported_sha256'] = '0'*64
    elif mutation == 'native-recipe':native['recipes']['trace_read_patches.py']['sha256'] = '0'*64
    elif mutation == 'native-stage':
        native['stages'] = [row for row in native['stages']
                            if not (row['recipe']=='trace_read_patches.py' and frame in row['sources'])]
    elif mutation == 'native-unknown':
        name = next(name for name in expected['native'] if name!=frame)
        native['sources'][name]['patched_sha256'] = '0'*64
    elif mutation == 'driver-output':driver['python_sources'][settings] = '0'*64
    elif mutation == 'driver-original':driver['sources'][settings]['original_sha256'] = '0'*64
    elif mutation == 'driver-stage':
        next(row for row in driver['stages'] if settings in row['sources'])['sources'][settings]['before_sha256'] = '0'*64
    elif mutation == 'driver-recipe':driver['recipes']['command_group_patches.py']['sha256'] = '0'*64
    elif mutation == 'driver-unknown':
        name = next(name for name in expected['driver'] if name!=settings)
        driver['python_sources'][name] = '0'*64
    elif mutation == 'frozen-native':expected['native'][frame]['patched'] = '0'*64
    else:expected['driver'][settings] = '0'*64
    with pytest.raises((AssertionError,ValueError,KeyError)):
        report.review_successors(native,driver,expected)


def test_composed_packages_independently_qualify_50_scoped_requirements():
    saved = canonical()
    actual = report.qualify({kind: Path(row['path']) for kind,row in saved['raw'].items()},
                            saved['runtime_image'], saved['source_revision'])
    assert actual == saved and len(actual['qualified_contracts']) == 50
    assert len(actual['checks']) == 95+50*4 and not actual['full_v05_accepted']
    for contract in actual['qualified_contracts']:
        assert all(supported_check(actual, contract+':'+d, d) for d in ('positive', 'boundary', 'failure', 'recovery'))


@pytest.mark.parametrize('mutation', ['profile', 'missing-case', 'native-byte',
                                    'added-driver-byte', 'added-data-byte', 'unknown-driver-file'])
def test_composed_capture_cannot_be_replaced_with_unqualified_evidence(tmp_path, mutation):
    saved = canonical()
    paths = {kind: Path(row['path']) for kind,row in saved['raw'].items()}
    raw = deepcopy(json.loads(paths['catalog'].read_bytes()))
    shutil.copytree(paths['catalog'].parent/'workspace', tmp_path/'workspace')
    shutil.copytree(paths['catalog'].parent/'inputs', tmp_path/'inputs')
    if mutation == 'profile':raw['composed'] = False
    elif mutation == 'missing-case':del raw['checks']['ConfirmCritical:failure']
    elif mutation == 'native-byte':
        name = next(n for n in raw['runtime_sources']['installed'] if n.endswith('/libspell_executor313.so'))
        raw['runtime_sources']['installed'][name] = '0'*64
    else:
        name = {'added-driver-byte': 'openbexi_spell_dss/telemetry_budget.py',
                'added-data-byte': 'openbexi_spell_dss/limit_files/normal.json',
                'unknown-driver-file': 'openbexi_spell_dss/unqualified.py'}[mutation]
        raw['runtime_sources']['installed'][name] = '0'*64
    workspace = tmp_path/'workspace'
    (workspace/'checks.json').write_text(json.dumps(raw['checks']), encoding='utf-8')
    (workspace/'runtime.json').write_text(json.dumps(raw['runtime_sources']), encoding='utf-8')
    raw['artifacts'] = {p.relative_to(workspace).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in workspace.rglob('*') if p.is_file()}
    path = tmp_path/'result.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    paths['catalog'] = path
    with pytest.raises((AssertionError, ValueError, KeyError)):
        report.qualify(paths, saved['runtime_image'], saved['source_revision'])
