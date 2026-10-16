"""Bind command diagnostics to the frozen, verified display/native image."""
import hashlib
import json
from pathlib import Path
import sys

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/command-group-patch')
ADDED=('openbexi_spell_dss/command_groups.py','openbexi_spell_dss/command_blocks.py','openbexi_spell_dss/command_results.py','openbexi_spell_dss/command_group_rpc.py','openbexi_dss_proxy/command_group.py')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {path.relative_to(SITE).as_posix():digest(path)
            for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss')
            for path in (SITE/package).rglob('*')
            if path.is_file() and (path.suffix in ('.py','.so') or path.parent.name=='bin')}


def capture():
    base=json.loads((EVIDENCE/'base.json').read_bytes())
    expected=dict(base['installed'])
    manifest=json.loads((EVIDENCE/'manifest.json').read_bytes())
    for name,row in manifest.items():
        if expected.get(name)!=row['preimage_sha256'] or digest(EVIDENCE/'original'/name)!=row['preimage_sha256']:
            raise ValueError('Command source preimage differs: '+name)
        if digest(EVIDENCE/'patched'/name)!=row['sha256']:
            raise ValueError('Command patched evidence differs: '+name)
        expected[name]=row['sha256']
    additions={}
    for name in ADDED:
        if name in expected:raise ValueError('Command addition replaces a base source')
        additions[name]=expected[name]=digest(EVIDENCE/'modules'/name)
    actual=sources()
    if actual!=expected:
        raise ValueError('Undeclared command image changes: '+repr(sorted(n for n in set(actual)|set(expected) if actual.get(n)!=expected.get(n))))
    for name,value in base['overlay']['files'].items():
        if digest(Path('/opt/command-catalog-patch')/name)!=value:
            raise ValueError('Historical display provenance changed')
    if digest(Path('/opt/command-catalog-patch/base.json'))!=base['base_sha256']:
        raise ValueError('Historical display base changed')
    return dict(profile='fresh-wheel-plus-display-command-catalog-and-group-overlays/1',integrated=base['integrated'],
        installed=actual,base_sha256=digest(EVIDENCE/'base.json'),base_profile=base['profile'],
        overlay=dict(manifest=manifest,added_sources=additions,files={
            p.relative_to(EVIDENCE).as_posix():digest(p) for p in EVIDENCE.rglob('*')
            if p.is_file() and p.name!='base.json'}))


if __name__=='__main__':
    if sys.argv[1:]==['--freeze-base']:
        sys.path.insert(0,'/opt/command-catalog-patch')
        from command_catalog_provenance import capture as previous
        EVIDENCE.mkdir(exist_ok=True)
        target=EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace command base')
        target.write_text(json.dumps(previous(),indent=2)+'\n')
    else:print(json.dumps(capture(),indent=2))
