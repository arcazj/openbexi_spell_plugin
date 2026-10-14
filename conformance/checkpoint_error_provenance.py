"""Verify original installation plus the one explicitly retained native overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay=Path('/opt/checkpoint-error-patch')
    base=json.loads((overlay/'baseline-installed.json').read_bytes())
    report=json.loads((overlay/'manifest.json').read_bytes())
    root=Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root/'manifest.json')==base['manifest_sha256']
    for name,expected in base['python_sources'].items():
        assert sha(root.parent/name)==expected,name
    for name,expected in base['native_artifacts'].items():
        assert sha(root/'bin'/name)==report['artifacts'].get(name,expected),name
    for label in ('original','ported','patched'):
        assert sha(overlay/label/report['source'])==report['sources'][label+'_sha256']
    for name,expected in report['recipes'].items():
        assert sha(overlay/name)==expected,name
    return dict(baseline=base,checkpoint_overlay=report)


def qualification_identity(record, inputs, normalized=None):
    """Validate either the retained overlay or an independently installed wheel."""
    if 'checkpoint_overlay' in record:
        overlay=record['checkpoint_overlay']
        if overlay['mode']!='fix':
            raise ValueError('Audit-only overlay does not qualify the correction')
        for name,path in [('checkpoint_error_patches.py','source_port/checkpoint_error_patches.py'),
                ('checkpoint_error_build.py','conformance/checkpoint_error_build.py'),
                ('incremental_native.py','distribution/incremental_native.py')]:
            if overlay['recipes'][name]!=inputs.get(path):
                raise ValueError('Overlay recipe differs from qualification input: '+name)
        return dict(kind='diagnostic-overlay',runtime_sha256=overlay['artifacts']['libspell_executor313.so'],
            evidence=overlay,limitation=overlay['limitation'])
    from installed_provenance import PROFILE, verify_capture
    if record.get('profile')!=PROFILE:
        raise ValueError('Missing checked runtime provenance')
    verify_capture(record,inputs,normalized)
    native=record['manifest']['composition']['native']
    source='lib/SPELL_EXC/src/SPELLframeManager.C'
    expected=dict(original_sha256='ae618d8e3239377b76d5e6e37782efc893e723dfc9c3daa8d89bb998cb6e1402',
        ported_sha256='31e1b73109a6266817f26ea0d1ad67935d81854c9e34c314aab75b33bda41fcf',
        patched_sha256='b0e8757c78d15479ec88d22497bbbef7706a70b41954211d44cebde6c6a4d9a7')
    if native['sources'].get(source)!=expected:
        raise ValueError('Installed frame-manager correction differs')
    if 'checkpoint_error_patches.py' not in native['recipes']:
        raise ValueError('Installed composition lacks checked recorder recipe')
    if 'host_native_sha256' in record and record['host_native_sha256'] not in (
            inputs.get('host_runtime/python/native.py'),(normalized or {}).get('host_runtime/python/native.py')):
        raise ValueError('IPC host source differs from qualification input')
    core={name:record[name] for name in ('profile','manifest_sha256','manifest','native_artifacts','python_sources')}
    core['driver_composition']=record.get('driver_composition')
    return dict(kind='installed-composition',runtime_sha256=record['native_artifacts']['libspell_executor313.so'],
        evidence=core,limitation='Fresh installed composition; behavior claims remain limited to the executed controls.')
