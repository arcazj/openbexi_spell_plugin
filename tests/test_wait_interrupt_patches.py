"""Bind the interruption fix to the previously qualified scheduler source."""
import hashlib
from pathlib import Path
import sys
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
import native_patches
import scheduler_patches
import wait_interrupt_patches as patch


def sources():
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        original=archive.read(patch.SOURCE)
    ported=native_patches.apply(patch.SOURCE,original)
    return original,scheduler_patches.apply(patch.SOURCE,original,ported)


def test_actual_scheduler_preimage_and_limited_change():
    original,ported=sources();patched=patch.apply(patch.SOURCE,original,ported)
    assert hashlib.sha256(patched).hexdigest()=='dc5db22f21100347bf9b71445fb1aef4ea8895a955d08b3d8ec6156a9ab750f7'
    signature=b'bool SPELLscheduler::timerCallback('
    before=ported[:ported.index(signature)]
    after=patched[:patched.index(signature)].replace(b'#include <mutex>\n',b'',1)
    assert before==after
    delimiter=b'//============================================================================='
    assert ported[ported.index(delimiter,ported.index(signature)):]==patched[patched.index(delimiter,patched.index(signature)):]


def test_changed_source_and_reapplying_rejected():
    original,ported=sources()
    for before,current in ((original+b' ',ported),(original,ported+b' '),(original,patch.apply(patch.SOURCE,original,ported))):
        with pytest.raises(ValueError):patch.apply(patch.SOURCE,before,current)
