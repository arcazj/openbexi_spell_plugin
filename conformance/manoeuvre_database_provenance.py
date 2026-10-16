"""Replay the one-source MMD correction over the exact accepted wheel inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/manoeuvre-database-patch')
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    if not EVIDENCE.exists():
        from installed_provenance import capture_application
        application=capture_application()
        recipes=application['integrated']['manifest']['composition']['native']['recipes']
        if 'manoeuvre_database_patches.py' not in recipes:raise ValueError('Composed manoeuvre recipe missing')
        return dict(application,profile='fresh-composed-manoeuvre-wheel/1')
    base=json.loads((EVIDENCE/'base.json').read_bytes())
    if base['profile']!='fresh-composed-display-command-wheel/1':raise ValueError('Manoeuvre diagnostic base differs')
    expected=dict(base['installed'])
    manifest=json.loads((EVIDENCE/'manifest.json').read_bytes())
    spec=importlib.util.spec_from_file_location('manoeuvre_recipe',EVIDENCE/'manoeuvre_database_patches.py')
    recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    if set(manifest)!=set(recipe.PREIMAGES):raise ValueError('Incomplete manoeuvre correction')
    for name,row in manifest.items():
        before,after=EVIDENCE/'original'/name,EVIDENCE/'patched'/name
        if sha(before)!=expected[name] or row['preimage_sha256']!=expected[name]:raise ValueError('Manoeuvre preimage differs')
        if recipe.apply(name,before.read_bytes())!=after.read_bytes() or sha(after)!=row['sha256']:
            raise ValueError('Manoeuvre correction replay differs')
        expected[name]=row['sha256']
    actual={path.relative_to(SITE).as_posix():sha(path)
        for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss')
        for path in (SITE/package).rglob('*') if path.is_file() and (path.suffix in ('.py','.so') or path.parent.name=='bin')}
    if actual!=expected:raise ValueError('Undeclared manoeuvre application changes')
    return dict(profile='fresh-composed-wheel-plus-manoeuvre-overlay/1',integrated=base['integrated'],
        installed=actual,base_sha256=sha(EVIDENCE/'base.json'),overlay=dict(manifest=manifest,files={
            path.relative_to(EVIDENCE).as_posix():sha(path) for path in EVIDENCE.rglob('*')
            if path.is_file() and path.name!='base.json' and '__pycache__' not in path.parts}))


if __name__=='__main__':
    if sys.argv[1:]==['--freeze-base']:
        from installed_provenance import capture_application
        target=EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace frozen manoeuvre base')
        target.write_text(json.dumps(capture_application(),indent=2)+'\n')
    else:print(json.dumps(capture(),indent=2))
