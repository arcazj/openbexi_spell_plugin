"""Reject source drift and bind the candidate race correction to original bytes."""
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import native_patches
import trace_read_patches as patch
import integrated_patches


def inputs():
    with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
        original = archive.read(patch.SOURCE)
    return original, native_patches.apply(patch.SOURCE, original)


def test_candidate_is_in_composition_and_preserves_native_count_read():
    original, ported = inputs()
    result = patch.apply(patch.SOURCE, original, ported)
    assert patch.SOURCE in integrated_patches.NATIVE_NAMES
    assert 'trace_read_patches.py' in integrated_patches.recipe_hashes()
    assert b'getCurrentTraceModel().getCurrentLineExecutions()' in result
    assert result != ported


def test_complete_composition_retains_the_checked_candidate(tmp_path):
    source = tmp_path / 'source'
    archive_path = ROOT / 'docs/reference/SPELL2.6.10-src.zip'
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(source)
    native_patches.apply_tree(source)
    report = integrated_patches.apply_native_tree(source, archive_path, tmp_path / 'evidence')
    original, ported = inputs()
    expected = patch.apply(patch.SOURCE, original, ported)
    assert (source / patch.SOURCE).read_bytes() == expected
    assert report['sources'][patch.SOURCE] == {
        'original_sha256': patch.ORIGINAL,
        'ported_sha256': patch.PORTED,
        'patched_sha256': integrated_patches.digest(expected),
    }
    stages = [row for row in report['stages'] if patch.SOURCE in row['sources']]
    assert len(stages) == 1 and stages[0]['recipe'] == 'trace_read_patches.py'


@pytest.mark.parametrize('changed', ['name', 'original', 'ported', 'already-patched'])
def test_unrecognized_source_is_rejected(changed):
    original, ported = inputs()
    name = patch.SOURCE
    if changed == 'name':
        name += '.other'
    elif changed == 'original':
        original += b'\n'
    elif changed == 'ported':
        ported += b'\n'
    else:
        ported = patch.apply(name, original, ported)
    with pytest.raises(ValueError, match='preimage'):
        patch.apply(name, original, ported)
