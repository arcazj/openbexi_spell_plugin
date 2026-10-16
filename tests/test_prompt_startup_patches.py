"""The transition correction must reject any unreviewed upstream source."""
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import child_lifecycle_patches
import native_patches
import prompt_control_patches
import prompt_timeout_patches
import prompt_startup_patches as patch


@pytest.mark.parametrize('changed', ['original', 'ported', 'name'])
def test_unreviewed_prompt_transition_preimage_is_rejected(changed):
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    ported = native_patches.apply(patch.SOURCE, original)
    for recipe in (child_lifecycle_patches, prompt_timeout_patches, prompt_control_patches):
        ported = recipe.apply(patch.SOURCE, original, ported)
    name = patch.SOURCE
    if changed == 'original': original += b'\n'
    elif changed == 'ported': ported += b'\n'
    else: name += '.other'
    with pytest.raises(ValueError, match='Prompt startup preimage'):
        patch.apply(name, original, ported)
