"""Retain and replay the memory overlay over the exact telemetry diagnostic."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/memory-features-patch')
ADDED=('openbexi_spell_dss/memory_images.py','openbexi_dss_proxy/memory_support.py')
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    base=json.loads((EVIDENCE/'base.json').read_bytes())
    if base['profile']!='fresh-composed-limit-telemetry-overlays/1':raise ValueError('Memory base must retain both diagnostic overlays')
    expected=dict(base['installed'])
    manifest=json.loads((EVIDENCE/'manifest.json').read_bytes())
    spec=importlib.util.spec_from_file_location('memory_recipe',EVIDENCE/'memory_feature_patches.py')
    recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    if set(manifest)!=set(recipe.PREIMAGES):raise ValueError('Incomplete memory overlay')
    for name,row in manifest.items():
        original,patched=EVIDENCE/'original'/name,EVIDENCE/'patched'/name
        if expected.get(name)!=row['preimage_sha256'] or digest(original)!=row['preimage_sha256']:
            raise ValueError('Memory preimage differs: '+name)
        if recipe.apply(name,original.read_bytes())!=patched.read_bytes() or digest(patched)!=row['sha256']:
            raise ValueError('Memory recipe replay differs: '+name)
        expected[name]=row['sha256']
    added={}
    for name in ADDED:
        if name in expected:raise ValueError('Memory addition replaces an existing source')
        expected[name]=added[name]=digest(EVIDENCE/'modules'/name)
    telemetry=Path('/opt/telemetry-features-patch')
    for name,value in base['overlay']['files'].items():
        if digest(telemetry/name)!=value:raise ValueError('Telemetry evidence changed: '+name)
    if digest(telemetry/'base.json')!=base['base_sha256']:raise ValueError('Telemetry base identity changed')
    limit=json.loads((telemetry/'base.json').read_bytes())
    for name,value in limit['overlay']['files'].items():
        if digest(Path('/opt/limit-features-patch')/name)!=value:raise ValueError('Limit evidence changed: '+name)
    if digest(Path('/opt/limit-features-patch/base.json'))!=limit['base_sha256']:raise ValueError('Limit base identity changed')
    actual={path.relative_to(SITE).as_posix():digest(path)
            for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss')
            for path in (SITE/package).rglob('*') if path.is_file()
            and (path.suffix in ('.py','.so') or path.parent.name in ('bin','limit_files'))}
    if actual!=expected:raise ValueError('Undeclared memory application changes: '+repr(sorted(
        name for name in set(actual)|set(expected) if actual.get(name)!=expected.get(name))))
    return dict(profile='fresh-composed-limit-telemetry-memory-overlays/1',integrated=base['integrated'],installed=actual,
        base_sha256=digest(EVIDENCE/'base.json'),base_profile=base['profile'],
        overlay=dict(manifest=manifest,added_sources=added,files={
            path.relative_to(EVIDENCE).as_posix():digest(path) for path in EVIDENCE.rglob('*')
            if path.is_file() and path.name!='base.json' and '__pycache__' not in path.parts}))


if __name__=='__main__':
    if sys.argv[1:]==['--freeze-base']:
        sys.path.insert(0,'/opt/telemetry-features-patch')
        from telemetry_features_provenance import capture as previous
        target=EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace frozen memory base')
        target.write_text(json.dumps(previous(),indent=2)+'\n')
    else:print(json.dumps(capture(),indent=2))
