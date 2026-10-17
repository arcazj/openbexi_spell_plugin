"""A later prompt stage cannot silently replace a previously reviewed body."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'conformance'))
import qualified_prompt_tail as tail


@pytest.fixture
def example(tmp_path, monkeypatch):
    name='lib/example.C';recipe='prompt_complete_patches.py';before='1'*64;after='2'*64
    body=b'checked recipe\n';digest=hashlib.sha256(body).hexdigest()
    source=dict(original='0'*64,ported=before,patched=after)
    proof=dict(passed=True,independent_reviews={key:{} for key in ('prompt','child','event')},
        native_changes={name:dict(before_sha256=before,after_sha256=after)},
        native={name:source},recipes={recipe:digest})
    encoded=json.dumps(proof).encode()
    donor=dict(commit='a'*40,path='review.json',sha256=hashlib.sha256(encoded).hexdigest())
    golden=tmp_path/'distribution/evidence/followup-qualified-sources.json'
    golden.parent.mkdir(parents=True);golden.write_text(json.dumps(dict(donors={'prompt_complete':donor})))
    recipe_path=tmp_path/'source_port'/recipe;recipe_path.parent.mkdir();recipe_path.write_bytes(body)
    native=dict(recipes={recipe:dict(sha256=digest)},
        stages=[dict(recipe=recipe,sources={name:dict(before_sha256=before,after_sha256=after)})],
        sources={name:{key+'_sha256':value for key,value in source.items()}})
    monkeypatch.setattr(tail,'ROOT',tmp_path)
    def committed(command,**kwargs):
        assert command==['git','show',donor['commit']+':'+donor['path']]
        return encoded
    monkeypatch.setattr(tail.subprocess,'check_output',committed)
    return native,name,before,after,golden,recipe_path


def test_reviewed_tail_keeps_the_exact_predecessor_and_committed_successor(example):
    native,name,before,after,*_=example
    assert tail.extend(native,name,before)==after


@pytest.mark.parametrize('change',['predecessor','stage','terminal','recipe','donor-digest','unreviewed'])
def test_unreviewed_or_changed_prompt_extension_is_rejected(example,change):
    native,name,before,_,golden,recipe=example
    native=deepcopy(native)
    if change=='predecessor':before='9'*64
    elif change=='stage':native['stages'][0]['sources'][name]['after_sha256']='9'*64
    elif change=='terminal':native['sources'][name]['patched_sha256']='9'*64
    elif change=='recipe':recipe.write_bytes(b'changed implementation')
    else:
        qualified=json.loads(golden.read_text())
        if change=='donor-digest':qualified['donors']['prompt_complete']['sha256']='9'*64
        else:qualified['donors'].clear()
        golden.write_text(json.dumps(qualified))
    with pytest.raises((AssertionError,KeyError)):
        tail.extend(native,name,before)


@pytest.mark.parametrize('defect',[None,'missing-review','broken-chain','changed-recipe','changed-terminal','missing-stage'])
def test_final_donor_requires_both_reviewed_prompt_successors(tmp_path,monkeypatch,defect):
    name='lib/helper.C';before='1'*64;middle='2'*64;after='3'*64
    recipes=('prompt_complete_patches.py','prompt_empty_option_patches.py')
    hashes={recipe:hashlib.sha256(recipe.encode()).hexdigest() for recipe in recipes}
    changes=[dict(recipe=recipe,source=name,before_sha256=start,after_sha256=end)
        for recipe,start,end in zip(recipes,(before,middle),(middle,after))]
    source=dict(original='0'*64,ported=before,patched=after)
    proof=dict(passed=True,independent_reviews={key:{} for key in
        ('prompt','child','event','command-group','memory','driver-extension')},
        native_changes=deepcopy(changes),native={name:source},recipes=hashes)
    if defect=='missing-review':proof['independent_reviews'].pop('event')
    encoded=json.dumps(proof).encode()
    donor=dict(commit='a'*40,path='review.json',sha256=hashlib.sha256(encoded).hexdigest())
    golden=tmp_path/'distribution/evidence/followup-qualified-sources.json'
    golden.parent.mkdir(parents=True);golden.write_text(json.dumps(dict(donors={'final_language':donor})))
    (tmp_path/'source_port').mkdir()
    for recipe in recipes:(tmp_path/'source_port'/recipe).write_bytes(recipe.encode())
    native=dict(recipes={recipe:dict(sha256=value) for recipe,value in hashes.items()},
        stages=[dict(recipe=row['recipe'],sources={name:{key:row[key] for key in ('before_sha256','after_sha256')}}) for row in changes],
        sources={name:{key+'_sha256':value for key,value in source.items()}})
    if defect=='broken-chain':native['stages'][1]['sources'][name]['before_sha256']='9'*64
    elif defect=='changed-recipe':(tmp_path/'source_port'/recipes[1]).write_bytes(b'unreviewed')
    elif defect=='changed-terminal':native['sources'][name]['patched_sha256']='9'*64
    elif defect=='missing-stage':native['stages'].pop()
    monkeypatch.setattr(tail,'ROOT',tmp_path)
    monkeypatch.setattr(tail.subprocess,'check_output',lambda *a,**k:encoded)
    if defect is None:assert tail.extend(native,name,before)==after
    else:
        with pytest.raises(AssertionError):tail.extend(native,name,before)
