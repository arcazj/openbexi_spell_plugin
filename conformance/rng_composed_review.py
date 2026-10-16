"""Review complete ranging source chains without changing the captured observer."""
from installed_provenance import verify_capture,verify_stages


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
        terminal='display_patches.py' if name.endswith('/ground.py') and 'display_patches.py' in manifest['recipes'] else recipe
        if 'ranging_complete_patches.py' in manifest['recipes']:
            terminal='ranging_complete_patches.py'
            if name.endswith('/ground.py'):
                terminal='memory_ranging_patches.py' if 'memory_ranging_patches.py' in manifest['recipes'] else 'ranging_reopen_patches.py'
        assert stages[-1]['recipe']==terminal,name
        assert stages[-1]['sources'][name]['after_sha256']==row['patched_sha256'],name
    return driver['sources']['openbexi_spell_dss/ground.py']

