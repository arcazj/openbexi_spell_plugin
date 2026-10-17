"""Bind retained negative controls to their original, immutable case sources."""
import hashlib
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'rng': ('rng_cases.py', '922d578ec14d4907b4cde2c0aaeee5a5ec5b6325',
            '36d59b73d7ae3727551886313c67f2387f934c20db733ce35bb8800a6569fdc7'),
    'rng_state': ('rng_state_cases.py', '669c1d794f26492c32b2e2031f4bb6b07fa6f136',
                  '536deefa7aabbea4e7609b2e6c4ba6edc75850101ddb43af51ca15c25091151b'),
}


def verify_baseline(baseline, family):
    """Review old failures without substituting them for current qualification.

    The original fixtures have one catalog device. The later composed fixture
    has two devices and explicit ranging paths; its passing controls still have
    to match the current CASES exactly in each report's qualify() function.
    """
    name, commit, expected = SOURCES[family]
    original = 'conformance/' + name
    path = ROOT / 'conformance/baselines' / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    assert baseline['inputs'][original] == expected, original
    source = runpy.run_path(str(path))
    assert set(baseline['checks']) == set(source['CASES'])
    for key, row in baseline['checks'].items():
        assert row['source'] == source['CASES'][key], key
        for field in ('contracts', 'dimension'):
            assert row[field] == source['METADATA'][key][field], (key, field)
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=expected,
                original_path=original, source_commit=commit,
                scope='Original historical negative controls only; current positive qualification uses current case sources.')
