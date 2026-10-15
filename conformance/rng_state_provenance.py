"""A declared diagnostic overlay, preserving the verified fresh-wheel identity."""
import hashlib
import json
from pathlib import Path
import sys
from rng_provenance import capture as rng_capture

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/rng-state-patch')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    result={}
    for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss'):
        for path in (SITE/package).rglob('*'):
            if path.is_file() and (path.suffix in ('.py','.so') or path.parent.name=='bin'):
                result[path.relative_to(SITE).as_posix()]=digest(path)
    return result


def capture():
    base_path=EVIDENCE/'base.json'
    if not base_path.exists():
        base=rng_capture()
        return dict(integrated=base['integrated'],installed=base['installed'],overlay=None,base_overlay=base['overlay'])
    base=json.loads(base_path.read_bytes())
    expected=dict(base['installed'])
    rows={}
    for directory in ('rng-state-patch',):
        root=Path('/opt',directory)
        manifest=json.loads((root/'manifest.json').read_bytes())
        for name,row in manifest.items():
            if row['preimage_sha256']!=expected.get(name):
                raise ValueError('Overlay chain preimage differs: '+name)
            if digest(root/'original'/name)!=row['preimage_sha256'] or digest(root/'patched'/name)!=row['sha256']:
                raise ValueError('Overlay retained bytes differ: '+name)
            expected[name]=row['sha256']
        rows[directory]=dict(manifest=manifest,files={p.relative_to(root).as_posix():digest(p)
            for p in root.rglob('*') if p.is_file() and p.name!='base.json'})
    actual=sources()
    if actual!=expected:
        raise ValueError('Undeclared diagnostic overlay source changes: '+repr(sorted(
            name for name in set(actual)|set(expected) if actual.get(name)!=expected.get(name))))
    integrated=base['integrated']
    if digest(SITE/'spell_native/manifest.json')!=integrated['manifest_sha256']:
        raise ValueError('Base installed-wheel manifest changed')
    for kind,record in integrated['manifest']['composition'].items():
        directory=SITE/'spell_native/provenance'/('integrated-'+kind)
        if digest(directory/'manifest.json')!=record['manifest_sha256']:
            raise ValueError('Base source composition changed')
        for name,row in record['recipes'].items():
            if digest(directory/'recipes'/name)!=row['sha256']:
                raise ValueError('Base composition recipe changed')
    return dict(integrated=integrated,installed=actual,overlay=rows['rng-state-patch'],base_overlay=base['base_overlay'],
                base_sha256=digest(base_path),profile='fresh-wheel-plus-declared-diagnostic-overlay/1')


if __name__=='__main__':
    if sys.argv[1:]==['--freeze-base']:
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        target=EVIDENCE/'base.json'
        if target.exists():
            raise ValueError('Refusing to replace frozen overlay base')
        target.write_text(json.dumps(capture(),indent=2)+'\n')
    else:
        print(json.dumps(capture(),indent=2))
