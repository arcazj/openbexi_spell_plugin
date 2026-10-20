"""Check that the distributed verifier detects corruption before reconstruction."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from release_artifacts import REASSEMBLE_SCRIPT, stage_artifact


def test_split_reassemble_and_reject_changed_part(tmp_path):
    source = tmp_path/'input.bin'
    source.write_bytes(bytes(range(256))*7)
    output = tmp_path/'release'
    output.mkdir()
    parts, joined = stage_artifact(source, output, asset_limit=600, part_size=400)
    assert len(parts) == 5 and b''.join(p.read_bytes() for p in parts) == source.read_bytes()
    manifest = dict(reassembled_artifacts={source.name:joined},
        assets={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in parts})
    (output/'RELEASE_MANIFEST.json').write_text(json.dumps(manifest))
    script=output/'reassemble.py'
    script.write_text(REASSEMBLE_SCRIPT)
    original=parts[2].read_bytes()
    parts[2].write_bytes(b'!' + original[1:])
    rejected=subprocess.run([sys.executable,str(script)],capture_output=True)
    assert rejected.returncode != 0 and not (output/source.name).exists()
    parts[2].write_bytes(original)
    subprocess.run([sys.executable,str(script)],capture_output=True,check=True)
    assert (output/source.name).read_bytes() == source.read_bytes()
    subprocess.run([sys.executable,str(script)],capture_output=True,check=True)


def test_small_asset_preserves_exact_bytes(tmp_path):
    source=tmp_path/'wheel.whl'
    source.write_bytes(b'exact release bytes')
    output=tmp_path/'release'
    output.mkdir()
    assets, joined=stage_artifact(source,output,asset_limit=100,part_size=50)
    assert joined is None and len(assets)==1 and assets[0].read_bytes()==source.read_bytes()
