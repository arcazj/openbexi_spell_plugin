"""Library configuration controls native search order without accepting unsafe paths."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('procedure_library',ROOT/'source_port/distribution/library.py')
library=importlib.util.module_from_spec(spec);spec.loader.exec_module(library)


def test_order_nested_folders_and_optional_absent_locations(tmp_path):
    assert library.priorities(tmp_path)==''
    (tmp_path/'spell-library.json').write_text(json.dumps(dict(schema='openbexi.spell.library/1',priorities=['Validation','Payload/Calibration','Bus'])))
    assert library.priorities(tmp_path)=='Validation\x1fPayload/Calibration\x1fBus'


@pytest.mark.parametrize('folders',[['../escape'],['/absolute'],['Bus\\Payload'],['C:/data'],['Bus','Bus'],['Bus\x1fPayload'],['Bus//Payload'],['.'],[''],[False],{},['Bus']*65])
def test_invalid_configuration_is_rejected(tmp_path,folders):
    (tmp_path/'spell-library.json').write_text(json.dumps(dict(schema='openbexi.spell.library/1',priorities=folders)))
    with pytest.raises(ValueError):library.priorities(tmp_path)


def test_duplicate_json_fields_are_rejected(tmp_path):
    (tmp_path/'spell-library.json').write_text('{"schema":"openbexi.spell.library/1","priorities":[],"priorities":["Bus"]}')
    with pytest.raises(ValueError,match='Duplicate'):library.priorities(tmp_path)
