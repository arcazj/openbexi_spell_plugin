"""The layered dictionary correction must reject source drift and repeat application."""
from pathlib import Path
import sys
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
import native_patches
import proc_dictionary_patches as patch


@pytest.mark.parametrize('name',patch.PREIMAGES)
def test_dictionary_patch_preserves_one_argument_evaluation(name):
    with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as archive:
        original=archive.read(name)
    ported=native_patches.apply(name,original)
    result=patch.apply(name,original,ported)
    before=ported.decode();after=result.decode()
    assert before.count('helper.eval(expression,false)')==after.count('helper.eval(expression,false)')==1
    assert after.count('"openbexi.spell.proc.arguments"')==2
    assert 'setText(DatabaseConstants::ARGS,getConfiguration().getArguments());' not in after
    assert after.count('loadExecutionEnvironment();')==before.count('loadExecutionEnvironment();')+1
    assert 'resetEntities = m_controller->shouldReload();' in after
    for bad_original,bad_ported in ((original+b'\n',ported),(original,ported+b'\n'),(original,result)):
        with pytest.raises(ValueError):patch.apply(name,bad_original,bad_ported)
