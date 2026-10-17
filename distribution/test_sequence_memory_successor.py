"""Historical memory evidence cannot silently authorize another driver body."""
import subprocess
from pathlib import Path

import pytest

import sequence_memory_successor as successor

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '7d50a6393413595293b27384db9506cd4cd2efef'


def test_sequence_successor_replays_exact_committed_predecessor():
    name = 'driver_plugin/src/'+successor.SOURCE
    before = subprocess.check_output(['git', 'show', BASELINE+':'+name], cwd=ROOT)
    assert successor.apply(before) == (ROOT/name).read_bytes()
    with pytest.raises(AssertionError):
        successor.apply(before+b'\n')
