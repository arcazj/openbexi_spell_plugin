"""Experimental compiler patches must reject changes to either source preimage."""
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import native_patches
import legacy_compare_patches as patch


@pytest.mark.parametrize('name', patch.PREIMAGES)
def test_exact_source_can_be_patched_but_preimage_drift_is_rejected(name):
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(name)
    ported = native_patches.apply(name, original)
    candidate = patch.apply(name, original, ported)
    assert candidate != ported
    for before, current in ((original + b'\n', ported), (original, ported + b'\n')):
        with pytest.raises(ValueError, match='preimage differs'):
            patch.apply(name, before, current)
    assert patch.apply(name, original, ported) == candidate
