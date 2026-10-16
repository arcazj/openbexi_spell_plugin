"""Identify the two changed source units and one diagnostic runtime library."""
import hashlib
import importlib.util
import json
from pathlib import Path

RECIPES={'proc_dictionary_patches.py':'source_port/proc_dictionary_patches.py',
    'proc_dictionary_build.py':'conformance/proc_dictionary_build.py',
    'incremental_native.py':'distribution/incremental_native.py'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def capture():
    overlay=Path('/opt/proc-dictionary-patch')
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
    for name,expected in report['recipes'].items():assert sha(overlay/name)==expected
    return dict(baseline=base,proc_dictionary_overlay=report)


def qualification_identity(record,inputs):
    from installed_provenance import verify_capture
    base=record['baseline'];verify_capture(base,inputs)
    overlay=record['proc_dictionary_overlay']
    assert overlay['passed'] and not overlay['full_release_accepted']
    assert set(overlay['sources'])=={'lib/SPELL_EXC/src/SPELLexecutorImpl.C','lib/SPELL_EXC/src/SPELLserviceImpl.C'}
    assert set(overlay['artifacts'])==set(overlay['original_artifacts'])=={'libspell_executor313.so'}
    assert overlay['recipes']=={name:inputs[path] for name,path in RECIPES.items()}
    for name,expected in overlay['original_artifacts'].items():
        assert expected==base['native_artifacts'][name] and overlay['artifacts'][name]!=expected
    return dict(kind='diagnostic-procedure-dictionary-overlay',baseline=base,evidence=overlay,
        limitation='One-library diagnostic overlay; fresh composition remains required')
