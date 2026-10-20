"""Verify original installation plus the one explicitly retained native overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay=Path('/opt/checkpoint-identity-patch')
    base=json.loads((overlay/'baseline-installed.json').read_bytes())
    report=json.loads((overlay/'manifest.json').read_bytes())
    root=Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root/'manifest.json')==base['manifest_sha256']
    for name,expected in base['python_sources'].items():
        assert sha(root.parent/name)==expected,name
    for name,expected in base['native_artifacts'].items():
        assert sha(root/'bin'/name)==report['artifacts'].get(name,expected),name
    for name,hashes in report['sources'].items():
        for label in ('original','ported','patched'):
            assert sha(overlay/label/name)==hashes[label+'_sha256']
    for name,expected in report['recipes'].items():
        assert sha(overlay/name)==expected,name
    return dict(baseline=base,identity_overlay=report)


EXPECTED_SOURCES = {'lib/SPELL_CTX/src/SPELLcontext.C': {'original_sha256': 'cf4576a8a95c543cddd53b8cb4f136a53e0114c1fc5bf3ebd6e39b1c0ff9129c',
                                      'patched_sha256': '18a6e1ac5a7556232df381b5084d615d91756a4bbdfa2a18aa2fb672108d18d7',
                                      'ported_sha256': '9618798e11004db0d42422b16806c3a7fbe0c53ebbe8a2bba05fa5e410940b81'},
 'lib/SPELL_EXC/src/SPELLframeManager.C': {'original_sha256': 'ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402',
                                           'patched_sha256': 'b0e8757c78d15479ec88d22497bbbef7706a70b41954211d44cebde6c6a4d9a7',
                                           'ported_sha256': '31e1b73109a6266817f26ea0d1ad67935d81854c9e34c314aab75b33bda41fcf'},
 'lib/SPELL_EXC/src/SPELLinterpreter.C': {'original_sha256': '3dd0a455669237924726637ca4b25ae524acfaf10d577b18a7c36258ad3f1256',
                                          'patched_sha256': '3365e1e1f0ae0c697e9dd7152ad8fd2d4d0b7e0f0f04b73ba82d3cafb165aade',
                                          'ported_sha256': '670726c1853be672353f5e35da579d0e1c1569ab457d7c0cfe3d4c29692e3b33'}}


def qualification_identity(record, inputs, normalized=None):
    """Bind exact corrections to a retained overlay or fresh installed sources."""
    recipes={'checkpoint_identity_patches.py':'source_port/checkpoint_identity_patches.py',
        'checkpoint_context_patches.py':'source_port/checkpoint_context_patches.py',
        'checkpoint_error_patches.py':'source_port/checkpoint_error_patches.py'}
    if 'identity_overlay' in record:
        overlay=record['identity_overlay']
        if overlay['sources']!=EXPECTED_SOURCES or overlay['mode']!='identity':
            raise ValueError('Diagnostic identity correction differs')
        if set(overlay['artifacts'])!={'libspell_executor313.so','SPELL-Context'}:
            raise ValueError('Diagnostic identity artifact set differs')
        if set(overlay['original_artifacts'])!=set(overlay['artifacts']):
            raise ValueError('Diagnostic original artifact set differs')
        for name,expected in overlay['original_artifacts'].items():
            if record['baseline']['native_artifacts'][name]!=expected or overlay['artifacts'][name]==expected:
                raise ValueError('Diagnostic baseline artifact differs: '+name)
        recipes.update({'checkpoint_identity_build.py':'conformance/checkpoint_identity_build.py',
            'incremental_native.py':'distribution/incremental_native.py'})
        if overlay['recipes']!={name:inputs.get(path) for name,path in recipes.items()}:
            raise ValueError('Diagnostic identity recipes differ from qualification inputs')
        return dict(kind='diagnostic-overlay',native_artifacts=overlay['artifacts'],evidence=overlay,
            limitation='Diagnostic overlay retains original package RECORD; distribution acceptance requires a fresh composed build')
    from installed_provenance import PROFILE,verify_capture,verify_stages
    if record.get('profile')!=PROFILE:
        raise ValueError('Missing installed checkpoint identity provenance')
    verify_capture(record,inputs,normalized)
    native=record['manifest']['composition']['native']
    verify_stages('native',native)
    for name,expected in EXPECTED_SOURCES.items():
        actual=native['sources'].get(name,{})
        final=expected['patched_sha256']
        if name=='lib/SPELL_EXC/src/SPELLframeManager.C' and 'trace_read_patches.py' in native['recipes']:
            final='d1e46bf91b8997a79b5cfd4bc24eb5f49a9db14a9e9b94df13c38cf16d397d05'
            trace=[stage['sources'].get(name) for stage in native['stages']
                   if stage['recipe']=='trace_read_patches.py' and name in stage['sources']]
            if trace!=[dict(before_sha256=expected['patched_sha256'],after_sha256=final)]:
                raise ValueError('Installed trace snapshot stage differs: '+name)
        if actual.get('original_sha256')!=expected['original_sha256'] or actual.get('patched_sha256')!=final:
            raise ValueError('Installed checkpoint correction differs: '+name)
        recipe={'lib/SPELL_CTX/src/SPELLcontext.C':'checkpoint_context_patches.py',
            'lib/SPELL_EXC/src/SPELLinterpreter.C':'checkpoint_identity_patches.py',
            'lib/SPELL_EXC/src/SPELLframeManager.C':'checkpoint_error_patches.py'}[name]
        if recipe not in native['recipes']:
            raise ValueError('Missing checked checkpoint recipe: '+recipe)
        stages=[stage['sources'].get(name) for stage in native['stages'] if stage['recipe']==recipe]
        if stages!=[dict(before_sha256=expected['ported_sha256'],after_sha256=expected['patched_sha256'])]:
            raise ValueError('Installed checkpoint stage differs: '+name)
    if record.get('host_native_sha256') not in (inputs.get('host_runtime/python/native.py'),
            (normalized or {}).get('host_runtime/python/native.py')) or not record.get('host_native_sha256'):
        raise ValueError('IPC host source differs from qualification input')
    core={name:record[name] for name in ('profile','manifest_sha256','manifest','native_artifacts','python_sources')}
    core['driver_composition']=record.get('driver_composition')
    return dict(kind='installed-composition',native_artifacts=record['native_artifacts'],evidence=core,
        limitation='Fresh installed source composition is verified; runtime claims remain limited to the executed controls')
