"""Bind native procedure diagnostics to a reproduced donor and exact replacement bytes."""
import hashlib,importlib.util,json,sys
from pathlib import Path

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/procedure-library-patch')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def capture():
    base=json.loads((EVIDENCE/'base.json').read_bytes())
    assert base['profile']=='fresh-composed-display-command-wheel/1'
    record=json.loads((EVIDENCE/'build.json').read_bytes())
    assert record['passed'] and record['original_link_reproduced']
    assert record['donor_runtime_sha256']==base['installed']['spell_native/bin/libspell_executor313.so']
    spec=importlib.util.spec_from_file_location('procedure_recipe',EVIDENCE/'procedure_library_patches.py')
    recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    assert sha(EVIDENCE/'procedure_library_patches.py')==record['recipe_sha256']
    assert sha(EVIDENCE/'original-child.C')==record['original_child_sha256']==recipe.PREIMAGES[recipe.SOURCE]
    assert recipe.apply(recipe.SOURCE,(EVIDENCE/'original-child.C').read_bytes())==(EVIDENCE/'patched-child.C').read_bytes()
    assert sha(EVIDENCE/'patched-child.C')==record['patched_child_sha256']
    expected=dict(base['installed'])
    expected['spell_native/bin/libspell_executor313.so']=record['runtime_sha256']
    for name,digest in record['modules'].items():
        assert name in ('spell_native/launcher.py','spell_native/library.py')
        assert sha(EVIDENCE/Path(name).name)==digest
        expected[name]=digest
    actual={p.relative_to(SITE).as_posix():sha(p)
        for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss')
        for p in (SITE/package).rglob('*') if p.is_file() and (p.suffix in ('.py','.so') or p.parent.name=='bin')}
    assert actual==expected,'Undeclared procedure diagnostic application changes'
    return dict(profile='fresh-composed-wheel-plus-procedure-library-overlay/1',integrated=base['integrated'],
        installed=actual,base_sha256=sha(EVIDENCE/'base.json'),overlay=dict(build=record,files={
            p.relative_to(EVIDENCE).as_posix():sha(p) for p in EVIDENCE.rglob('*')
            if p.is_file() and p.name!='base.json' and '__pycache__' not in p.parts}))


if __name__=='__main__':print(json.dumps(capture(),indent=2))
