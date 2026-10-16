"""Whole SPECIAL rows retain every native dimension and original inventory identity."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from aggregate_support import DIMENSIONS, dimensional_mapping
from special_complete_report import MAP, spelling
from memory_complete_cases import CASES as MEMORY
from ranging_complete_cases import CASES as RANGING


def test_all_remaining_special_rows_have_complete_feature_dependencies():
    baseline=json.loads(subprocess.check_output(['git','show',
        'ffc6d660a111e9478f8a1d0280651f37d2dfb10d:conformance/coverage.json'],cwd=ROOT))
    expected={r['id'] for r in baseline['rows'] if r['status']!='QUALIFIED' and
        (r['package']=='SPECIAL' or r['id'].startswith('CMP-LRM244-CONSTANT-RANGING-STATE-')
         or r['id']=='CMP-LRM244-SECTION-4-18-4-128')}
    assert {'CMP-LRM244-'+name for name in MAP}==expected and len(expected)==45
    for dependencies in MAP.values():
        assert len(set(dependencies))==len(dependencies)
        for suite,feature in dependencies:
            assert all(feature+':'+dimension in {'memory':MEMORY,'ranging':RANGING}[suite]
                       for dimension in DIMENSIONS)


@pytest.mark.parametrize('defect',['missing','failed','dimension'])
def test_whole_memory_mapping_rejects_any_missing_reviewed_dimension(defect):
    reviewed={'memory':json.loads((ROOT/'conformance/evidence/memory_complete_review.json').read_bytes())}
    mapping={name:deps for name,deps in MAP.items() if all(suite=='memory' for suite,_ in deps)}
    accepted=dimensional_mapping(mapping,reviewed)
    from check import supported_check
    roots={key:row for key,row in accepted.items() if row['contracts']}
    assert len(roots)==len(mapping)*4
    assert all(supported_check({'checks':accepted},key,row['dimension']) for key,row in roots.items())
    for key in ('report:failure','compare:boundary','lookup:recovery','tmtc:positive'):
        changed=deepcopy(reviewed)
        if defect=='missing':del changed['memory']['checks'][key]
        elif defect=='failed':changed['memory']['checks'][key]['passed']=False
        else:changed['memory']['checks'][key]['dimension']='unclassified'
        with pytest.raises((KeyError,AssertionError)):dimensional_mapping(mapping,changed)


def test_original_manual_and_archive_resolve_singular_index_typo():
    result=spelling()
    assert result['pages']==[101,104] and result['member_sha256']
