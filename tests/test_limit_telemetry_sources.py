"""Complete wheel records include data resources as well as executable sources."""
import base64
import csv
import hashlib
import io
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'conformance'),str(ROOT/'driver_plugin/src')]
from limit_telemetry_sources import wheel_sources


def package(path, mutation):
    entries = {'openbexi_spell_dss/limits.py':b'value=1\n',
               'openbexi_spell_dss/limit_files/normal.json':b'{"normal":true}\n'}
    record = 'driver-1.dist-info/RECORD'
    stream = io.StringIO(newline='')
    writer = csv.writer(stream,lineterminator='\n')
    for name,content in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
        writer.writerow((name,'sha256='+digest,len(content)))
    writer.writerow((record,'',''));entries[record]=stream.getvalue().encode()
    if mutation == 'changed-resource':entries['openbexi_spell_dss/limit_files/normal.json']=b'{}\n'
    if mutation == 'unrecorded-resource':entries['openbexi_spell_dss/limit_files/other.json']=b'{}\n'
    with zipfile.ZipFile(path,'w') as archive:
        for name,content in entries.items():archive.writestr(name,content)
        if mutation == 'duplicate-resource':
            with pytest.warns(UserWarning,match='Duplicate name'):
                archive.writestr('openbexi_spell_dss/limit_files/normal.json',b'{}\n')
    return entries


def test_complete_resource_and_source_record_is_read_without_extraction(tmp_path):
    path=tmp_path/'driver.whl';expected=package(path,'unchanged')
    assert wheel_sources(path)==expected


@pytest.mark.parametrize('mutation',['changed-resource','unrecorded-resource','duplicate-resource'])
def test_resource_drift_or_ambiguous_record_is_rejected(tmp_path,mutation):
    path=tmp_path/'driver.whl';package(path,mutation)
    with pytest.raises(AssertionError):wheel_sources(path)
