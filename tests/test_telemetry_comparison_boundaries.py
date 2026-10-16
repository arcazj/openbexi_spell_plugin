"""Original source fixes the endpoint policy independently of the new probes."""
import hashlib
from pathlib import Path
import textwrap
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'


@pytest.fixture(scope='module')
def original_comparisons():
    path = ROOT/'docs/reference/SPELL2.6.10-src.zip'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA
    with zipfile.ZipFile(path) as archive:
        source = archive.read('src/spell/spell/lib/adapter/tm.py').decode('utf-8')
    namespace = {'INTERFACE_DEFAULTS': {'RelTolerance':0}, 'RelTolerance':'RelTolerance', 'DriverException':ValueError}
    for name in ('__c_btw', '__c_nbtw'):
        start = source.index('    def '+name+'(')
        end = source.index('\n    def ', start+1)
        exec(compile(textwrap.dedent(source[start:end]), name, 'exec'), namespace)
    return namespace['__c_btw'], namespace['__c_nbtw']


@pytest.mark.parametrize('value,lower,upper,strict,expected', [
    (28,28,28,False,(True,True)), (28,28,28,True,(False,False)),
    (28,27,29,False,(True,False)), (28,27,29,True,(True,False)),
    (28,29,30,False,(False,True)), (28,29,30,True,(False,True)),
    (28,28,29,False,(True,True)), (28,28,29,True,(False,False)),
])
def test_original_between_and_not_between_boundary_policy(original_comparisons,value,lower,upper,strict,expected):
    actual = tuple(function(None,value,lower,upper,strict,0) for function in original_comparisons)
    assert actual == expected
