"""Identify the changed scheduler source unit and one diagnostic runtime library."""
import hashlib
import importlib.util
import json
from pathlib import Path

RECIPES={'wait_interrupt_patches.py':'source_port/wait_interrupt_patches.py',
    'wait_interrupt_build.py':'conformance/wait_interrupt_build.py',
    'incremental_native.py':'distribution/incremental_native.py',
    'wait_interrupt_probe.py':'conformance/wait_interrupt_probe.py'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def capture():
    overlay=Path('/opt/wait-interrupt-patch')
    base=json.loads((overlay/'baseline-installed.json').read_bytes())
    report=json.loads((overlay/'manifest.json').read_bytes())
    root=Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root/'manifest.json')==base['manifest_sha256']
    for name,expected in base['python_sources'].items():assert sha(root.parent/name)==expected,name
    for name,expected in base['native_artifacts'].items():
        assert sha(root/'bin'/name)==report['artifacts'].get(name,expected),name
    if base['driver_composition'] is not None:
        from openbexi_dss_proxy.provenance import capture as driver_capture
        assert driver_capture(base['manifest']['composition']['native']['recipes'])==base['driver_composition']
    for name,record in report['sources'].items():
        for label in ('original','ported','patched'):
            assert sha(overlay/label/name)==record[label+'_sha256']
    assert sha(overlay/'compiled/incremental-build.json')==report['incremental_build_sha256']
    assert sha(overlay/'probes/result.json')==report['probes_sha256']
    assert json.loads((overlay/'probes/result.json').read_bytes())==report['probes']
    for label,probe in report['probes']['probes'].items():
        assert sha(overlay/'probes'/(label+'-probe.cpp'))==probe['source_sha256']
        assert sha(overlay/'probes'/(label+'-probe'))==probe['binary_sha256']
    for name,expected in report['recipes'].items():assert sha(overlay/name)==expected
    return dict(baseline=base,wait_interrupt_overlay=report)


def qualification_identity(record,inputs):
    from installed_provenance import verify_capture
    base=record['baseline'];verify_capture(base,inputs)
    overlay=record['wait_interrupt_overlay']
    assert overlay['passed'] and not overlay['full_release_accepted']
    assert set(overlay['sources'])=={'lib/SPELL_EXC/src/SPELLscheduler.C'}
    assert set(overlay['artifacts'])==set(overlay['original_artifacts'])=={'libspell_executor313.so'}
    assert overlay['recipes']=={name:inputs[path] for name,path in RECIPES.items()}
    for name,expected in overlay['original_artifacts'].items():
        assert expected==base['native_artifacts'][name] and overlay['artifacts'][name]!=expected
    assert overlay['probes']['passed']
    for label,probe in overlay['probes']['probes'].items():
        assert probe['exit_code']==(1 if label=='original' else 0)
        assert probe['observation']['paused_checks']==(4 if label=='original' else 0)
    return dict(kind='diagnostic-wait-interruption-overlay',baseline=base,evidence=overlay,
        limitation='One-library diagnostic overlay; fresh composition remains required')
