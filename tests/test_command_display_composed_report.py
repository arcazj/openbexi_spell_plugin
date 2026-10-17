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
