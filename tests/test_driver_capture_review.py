"""Installed RECORD metadata must not invalidate a verified wheel capture."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'), str(ROOT/'driver_plugin/src')]
import limit_telemetry_sources as sources


@pytest.mark.parametrize('change', [
    'valid', 'manifest', 'digest', 'profile', 'missing-count', 'low-count',
    'boolean-count', 'extra-field',
])
def test_installed_capture_preserves_verified_composition(monkeypatch, change):
    expected = {'profile': 'repository-dss-integrated-wheel/1',
                'manifest_sha256': 'a'*64, 'manifest': {'source': 'verified'}}
    driver = {'module.py': b'code', 'dist-info/METADATA': b'metadata',
              'dist-info/RECORD': b'record'}
    recipes = {'recipe.py': {'sha256': 'b'*64}}

    def verify(read, declared):
        assert read('module.py') == b'code' and declared == recipes
        return expected

    monkeypatch.setattr(sources, 'verify_driver', verify)
    captured = dict(deepcopy(expected), record_files_verified=5)
    if change == 'manifest': captured['manifest']['source'] = 'tampered'
    elif change == 'digest': captured['manifest_sha256'] = 'c'*64
    elif change == 'profile': captured['profile'] = 'other'
    elif change == 'missing-count': captured.pop('record_files_verified')
    elif change == 'low-count': captured['record_files_verified'] = 1
    elif change == 'boolean-count': captured['record_files_verified'] = True
    elif change == 'extra-field': captured['unknown'] = 'undeclared'
    if change == 'valid':
        sources.verify_driver_capture(driver, recipes, captured)
    else:
        with pytest.raises(AssertionError):
            sources.verify_driver_capture(driver, recipes, captured)
