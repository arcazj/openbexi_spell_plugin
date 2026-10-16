"""The listener correction accepts only the exact reviewed native source."""
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import native_patches
import context_snapshot_patches as patch


@pytest.mark.parametrize('changed', ['original','ported','name'])
def test_unreviewed_preimage_is_rejected(changed):
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    ported = native_patches.apply(patch.SOURCE, original)
    name = patch.SOURCE
    if changed == 'original': original += b'\n'
    elif changed == 'ported': ported += b'\n'
    else: name += '.other'
    with pytest.raises(ValueError, match='snapshot preimage'):
        patch.apply(name, original, ported)
