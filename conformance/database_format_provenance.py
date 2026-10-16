"""Bind three database corrections to the unchanged telemetry/limit runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/database-format-patch')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def capture():
    base=json.loads((EVIDENCE/'base.json').read_bytes())
    if base['profile']!='fresh-composed-limit-telemetry-overlays/1':raise ValueError('Database format base differs')
    expected=dict(base['installed'])
    manifest=json.loads((EVIDENCE/'manifest.json').read_bytes())
    spec=importlib.util.spec_from_file_location('database_format_recipe',EVIDENCE/'database_format_patches.py')
    recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    if set(manifest)!=set(recipe.PREIMAGES):raise ValueError('Incomplete database format correction')
    for name,row in manifest.items():
        before,after=EVIDENCE/'original'/name,EVIDENCE/'patched'/name
        if sha(before)!=expected[name] or row['preimage_sha256']!=expected[name]:raise ValueError('Database preimage differs')
        if recipe.apply(name,before.read_bytes())!=after.read_bytes() or sha(after)!=row['sha256']:
            raise ValueError('Database correction replay differs')
        expected[name]=row['sha256']
    parent=Path('/opt/telemetry-features-patch')
    if sha(parent/'base.json')!=base['base_sha256']:raise ValueError('Telemetry overlay base changed')
    for name,value in base['overlay']['files'].items():
        if sha(parent/name)!=value:raise ValueError('Telemetry overlay changed: '+name)
    actual={path.relative_to(SITE).as_posix():sha(path)
        for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss')
        for path in (SITE/package).rglob('*') if path.is_file()
        and (path.suffix in ('.py','.so') or path.parent.name in ('bin','limit_files'))}
    if actual!=expected:raise ValueError('Undeclared database application changes')
    return dict(profile='fresh-composed-limit-telemetry-database-format-overlays/1',
        integrated=base['integrated'],installed=actual,base_sha256=sha(EVIDENCE/'base.json'),
        overlay=dict(manifest=manifest,files={path.relative_to(EVIDENCE).as_posix():sha(path)
            for path in EVIDENCE.rglob('*') if path.is_file() and path.name!='base.json' and '__pycache__' not in path.parts}))


if __name__=='__main__':
    if sys.argv[1:]==['--freeze-base']:
        sys.path.insert(0,'/opt/telemetry-features-patch')
        from telemetry_features_provenance import capture as parent_capture
        target=EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace frozen database base')
        target.write_text(json.dumps(parent_capture(),indent=2)+'\n')
    else:print(json.dumps(capture(),indent=2))
