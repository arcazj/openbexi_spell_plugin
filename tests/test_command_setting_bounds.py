"""Huge integers must fail as driver validation errors before any RPC."""
import ast
import math
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
from command_group_patches import apply


class DriverError(Exception):
    pass


class FakeTime:
    pass


@pytest.fixture
def normalize():
    name = 'openbexi_dss_proxy/command_settings.py'
    tree = ast.parse(apply(name, (ROOT/'driver_plugin/src'/name).read_bytes()))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    namespace = dict(math=math, TIME=FakeTime, DriverException=DriverError, POLICY=set())
    exec(compile(tree, name, 'exec'), namespace)
    return namespace['normalize']


@pytest.mark.parametrize('key', ['Timeout','SendDelay','Time','ReleaseTime'])
@pytest.mark.parametrize('value', [2**4096, -(2**4096), float('inf'), float('nan'), True])
def test_invalid_numeric_settings_have_driver_errors_and_leave_input_intact(normalize,key,value):
    settings = {key:value}
    with pytest.raises(DriverError):
        normalize(settings)
    assert settings.keys() == {key} and settings[key] is value
    assert normalize({'Timeout':3600}) == {'Timeout':3600}


def test_timeout_upper_boundary_and_next_integer(normalize):
    assert normalize({'Timeout':3600}) == {'Timeout':3600}
    with pytest.raises(DriverError):
        normalize({'Timeout':3601})
