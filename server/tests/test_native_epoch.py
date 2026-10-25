"""Native packet identity survives delayed delivery across a host epoch change."""

import importlib.util
from pathlib import Path
import uuid

import pytest


spec = importlib.util.spec_from_file_location(
    "epoch_connection",
    Path(__file__).resolve().parents[2] / "host_runtime/python/epoch_connection.py",
)
assert spec is not None and spec.loader is not None
epoch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epoch)


def test_original_packet_keeps_a_while_new_packet_gets_b(tmp_path):
    path = tmp_path / "epoch"
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    path.write_text(a)
    packet = epoch.capture_metadata((("trace", "original"),), path)
    path.write_text(b)
    assert epoch.capture_metadata(packet, path) == packet
    assert dict(packet)[epoch.HEADER] == a
    assert epoch.capture_metadata(None, path) == ((epoch.HEADER, b),)


@pytest.mark.parametrize("marker", ["", "bad", "A" * 36, str(uuid.uuid4()) + "\n"])
def test_bad_epoch_cannot_dispatch_new_work(tmp_path, marker):
    path = tmp_path / "epoch"
    path.write_text(marker)
    with pytest.raises(ValueError):
        epoch.capture_metadata(None, path)


def test_duplicate_epoch_is_not_repaired_into_authorized_work(tmp_path):
    packet = ((epoch.HEADER, "a"), (epoch.HEADER, "b"))
    assert epoch.capture_metadata(packet, tmp_path / "missing") == packet
