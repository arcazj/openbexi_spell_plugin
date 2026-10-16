"""Verify ranging sources in composed wheels or retained diagnostic overlays."""
import hashlib
import json
from pathlib import Path
import sys
from installed_provenance import capture as installed_capture, verify_capture, verify_stages

SITE=Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE=Path('/opt/rng-patch')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    result={}
    for package in ('spell','spell_native','openbexi_dss_proxy','openbexi_spell_dss'):
        for path in (SITE/package).rglob('*'):
            if path.is_file() and (path.suffix in ('.py','.so') or path.parent.name=='bin'):
                result[path.relative_to(SITE).as_posix()]=digest(path)
    return result


def verify_composed(runtime, inputs, normalized):
    """Require actual composed helper, proxy and Ground bytes without an overlay."""
    assert runtime.get('overlay') is None and runtime.get('base_overlay') is None
    record=runtime['integrated']
    assert record and record['driver_composition']
    verify_capture(record,inputs,normalized)
    python=record['manifest']['composition']['python']
    driver=record['driver_composition']['manifest']
    for kind,manifest in (('python',python),('driver',driver)):
        assert {'rng_patches.py','rng_state_patches.py'} <= set(manifest['recipes'])
        assert manifest['stages'],kind
    verify_stages('python',python)
    state={name:row['original_sha256'] for name,row in driver['sources'].items()}
    for stage in driver['stages']:
        assert stage['recipe'] in driver['recipes']
        for name,row in stage['sources'].items():
            assert state.get(name)==row['before_sha256'],name
            state[name]=row['after_sha256']
    assert state=={name:row['patched_sha256'] for name,row in driver['sources'].items()}
    for name,recipe,manifest,installed in (
        ('spell/lang/helpers/rnghelper.py','rng_patches.py',python,record['python_sources']),
        ('openbexi_dss_proxy/ranging.py','rng_patches.py',driver,driver['python_sources']),
        ('openbexi_spell_dss/ground.py','rng_state_patches.py',driver,driver['python_sources'])):
        row=manifest['sources'][name]
        assert runtime['installed'][name]==installed[name]==row['patched_sha256'],name
        stages=[stage for stage in manifest['stages'] if name in stage['sources']]
        assert stages and any(stage['recipe']==recipe for stage in stages),name
        if 'ranging_complete_patches.py' in manifest['recipes']:
            final='ranging_complete_patches.py'
            if name.endswith('/ground.py'):
                final='memory_feature_patches.py' if 'memory_feature_patches.py' in manifest['recipes'] else 'ranging_reopen_patches.py'
            assert stages[-1]['recipe']==final,name
        else:assert stages[-1]['recipe']==recipe,name
        assert stages[-1]['sources'][name]['after_sha256']==row['patched_sha256'],name
    return driver['sources']['openbexi_spell_dss/ground.py']


def capture():
    base_path=EVIDENCE/'base.json'
    if not base_path.exists():
        return dict(integrated=installed_capture(),installed=sources(),overlay=None)
    base=json.loads(base_path.read_bytes())
    expected=dict(base['installed'])
    rows={}
    for directory in ('rng-patch',):
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
    return dict(integrated=integrated,installed=actual,overlay=rows['rng-patch'],
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
