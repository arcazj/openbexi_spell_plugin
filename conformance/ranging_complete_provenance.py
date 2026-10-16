"""Replay declared ranging changes over every installed original wheel file."""
import hashlib,importlib.util,json,sys
from pathlib import Path

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/ranging-complete-patch')
ADDED=('openbexi_spell_dss/ranging_complete.py','openbexi_dss_proxy/ranging_complete.py')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def capture():
    if not EVIDENCE.exists():
        from installed_provenance import capture_application
        application=capture_application()
        recipes=application['integrated']['manifest']['composition']['native']['recipes']
        if not {'ranging_complete_patches.py','ranging_reopen_patches.py'}<=set(recipes):raise ValueError('Composed ranging recipes are absent')
        return dict(application,profile='fresh-composed-ranging-wheel/1')
    base=json.loads((EVIDENCE/'base.json').read_bytes())
    if base['profile']!='fresh-composed-display-command-wheel/1':raise ValueError('Ranging base differs')
    expected=dict(base['installed'])
    manifest=json.loads((EVIDENCE/'manifest.json').read_bytes())
    spec=importlib.util.spec_from_file_location('ranging_recipe',EVIDENCE/'ranging_complete_patches.py')
    recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    if set(manifest)!=set(recipe.PREIMAGES):raise ValueError('Incomplete ranging correction')
    for name,row in manifest.items():
        before,after=EVIDENCE/'original'/name,EVIDENCE/'patched'/name
        if sha(before)!=expected[name] or row['preimage_sha256']!=expected[name]:raise ValueError('Ranging preimage differs')
        if recipe.apply(name,before.read_bytes())!=after.read_bytes() or sha(after)!=row['sha256']:
            raise ValueError('Ranging correction replay differs')
        expected[name]=row['sha256']
    added={}
    for name in ADDED:
        if name in expected:raise ValueError('Ranging addition replaces existing source')
        expected[name]=added[name]=sha(EVIDENCE/'modules'/name)
    actual={path.relative_to(SITE).as_posix():sha(path)
        for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss')
        for path in (SITE/package).rglob('*') if path.is_file() and (path.suffix in ('.py','.so') or path.parent.name=='bin')}
    if actual!=expected:raise ValueError('Undeclared ranging application changes')
    return dict(profile='fresh-composed-wheel-plus-ranging-overlay/1',integrated=base['integrated'],installed=actual,
        base_sha256=sha(EVIDENCE/'base.json'),overlay=dict(manifest=manifest,added_sources=added,files={
            path.relative_to(EVIDENCE).as_posix():sha(path) for path in EVIDENCE.rglob('*')
            if path.is_file() and path.name!='base.json' and '__pycache__' not in path.parts}))


if __name__=='__main__':
    if sys.argv[1:]==['--freeze-base']:
        from installed_provenance import capture_application
        target=EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace frozen ranging base')
        target.write_text(json.dumps(capture_application(),indent=2)+'\n')
    else:print(json.dumps(capture(),indent=2))
