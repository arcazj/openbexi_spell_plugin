"""Packaging integrity checks, separate from native behavior qualification."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('stable_wheel', Path(__file__).with_name('stable_wheel.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_package(root, volatile):
    binary = b'\x7fELF-preserve-executable-content'
    native = root / 'src/spell_native/bin/native'
    native.parent.mkdir(parents=True)
    native.write_bytes(binary)
    manifest = {'qualification_sha256': str(volatile), 'archive_sha256': 'archive',
                'inputs': {'record_native.py': 'recorder'}, 'native_artifacts': {'native': module.digest(binary)},
                'python_sources': {'spell/__init__.py': module.digest(b'# native\n')}}
    report = {'executor_runtime': {'tests': 23}, 'context_runtime': {'tests': 10}, 'volatile': volatile}
    entries = {'spell_native/bin/native': binary,
               'spell/__init__.py': b'# native\n',
               'spell_native/manifest.json': json.dumps(manifest).encode(),
               'spell_native/provenance/NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json': json.dumps(report).encode(),
               'openbexi_spell_source-0.3.0.dist-info/RECORD': b'',
               'openbexi_spell_source-0.3.0.dist-info/licenses/GPL-3.0.txt': b'preserved license'}
    wheels = root / 'wheels'
    wheels.mkdir()
    with zipfile.ZipFile(wheels / 'candidate.whl', 'w') as archive:
        for name, content in entries.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o100755 if name.endswith('/native') else 0o100644) << 16
            archive.writestr(info, content)
    return entries


def test_independent_report_variation_does_not_change_payload_and_record(tmp_path):
    first = fixture_package(tmp_path / 'a', {'pid': 100, 'seconds': 2.7})
    fixture_package(tmp_path / 'b', {'pid': 999, 'seconds': 3.1})
    a = module.stabilize(tmp_path / 'a', tmp_path / 'a-out')
    b = module.stabilize(tmp_path / 'b', tmp_path / 'b-out')
    assert a['sha256'] == b['sha256']
    with zipfile.ZipFile(tmp_path / 'a-out/wheels/candidate.whl') as archive:
        assert archive.read('spell_native/bin/native') == first['spell_native/bin/native']
        assert archive.getinfo('spell_native/bin/native').external_attr >> 16 == 0o100755
        license_name = 'openbexi_spell_source-0.3.0.dist-info/licenses/GPL-3.0.txt'
        assert archive.read(license_name) == b'preserved license'
        record_name = 'openbexi_spell_source-0.3.0.dist-info/RECORD'
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
        assert {row[0] for row in rows} == set(archive.namelist())
        for name, digest, size in rows:
            if name == record_name:
                assert (digest, size) == ('', '')
                continue
            content = archive.read(name)
            expected = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
            assert digest == 'sha256=' + expected and int(size) == len(content)


def test_native_content_mismatch_prevents_success(tmp_path):
    fixture_package(tmp_path / 'input', {})
    (tmp_path / 'input/src/spell_native/bin/native').write_bytes(b'wrong executable')
    with pytest.raises(AssertionError):
        module.stabilize(tmp_path / 'input', tmp_path / 'failed')
    assert not (tmp_path / 'failed/package-result.json').exists()
