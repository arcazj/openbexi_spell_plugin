"""Verify the explicit one-library prompt diagnostic overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path

RECIPES = {'prompt_startup_patches.py': 'source_port/prompt_startup_patches.py',
    'prompt_startup_build.py': 'conformance/prompt_startup_build.py',
    'prompt_startup_probe.py': 'conformance/prompt_startup_probe.py',
    'incremental_native.py': 'distribution/incremental_native.py'}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay = Path('/opt/prompt-startup-patch')
    base = json.loads((overlay / 'baseline-installed.json').read_bytes())
    report = json.loads((overlay / 'manifest.json').read_bytes())
    root = Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root / 'manifest.json') == base['manifest_sha256']
    for name, expected in base['python_sources'].items():
        assert sha(root.parent / name) == expected, name
    for name, expected in base['native_artifacts'].items():
        assert sha(root / 'bin' / name) == report['artifacts'].get(name, expected), name
    for label, field in [('original','original_sha256'), ('ported','preimage_sha256'), ('patched','patched_sha256')]:
        assert sha(overlay / (label + '.C')) == report[field]
    assert sha(overlay / 'compiled/incremental-build.json') == report['incremental_build_sha256']
    assert sha(overlay / 'probes/result.json') == report['probes_sha256']
    assert json.loads((overlay / 'probes/result.json').read_bytes()) == report['probes']
    for label, probe in report['probes']['probes'].items():
        assert sha(overlay / 'probes' / (label + '-probe.cpp')) == probe['source_sha256']
        assert sha(overlay / 'probes' / (label + '-probe')) == probe['binary_sha256']
    for name, expected in report['recipes'].items():
        assert sha(overlay / name) == expected
    return dict(baseline=base, prompt_startup_overlay=report)


def qualification_identity(record, inputs):
    from installed_provenance import verify_capture
    base = record['baseline']
    verify_capture(base, inputs)
    overlay = record['prompt_startup_overlay']
    assert overlay['passed'] and not overlay['full_release_accepted']
    assert set(overlay['artifacts']) == set(overlay['original_artifacts']) == {'libspell_executor313.so'}
    assert overlay['recipes'] == {name: inputs[path] for name, path in RECIPES.items()}
    for name, expected in overlay['original_artifacts'].items():
        assert expected == base['native_artifacts'][name] and overlay['artifacts'][name] != expected
    probes = overlay['probes']
    assert probes['passed'] and set(probes['probes']) == {'original','patched'}
    for label, probe in probes['probes'].items():
        assert probe['exit_code'] == (1 if label == 'original' else 0)
        assert set(probe['observation']) == {'startup', 'cancel'}
        for observation in probe['observation'].values():
            assert observation['winner_preserved']
            assert observation['ack_during_transition'] is (label == 'patched')
    return dict(kind='diagnostic-prompt-startup-overlay', baseline=base, evidence=overlay,
        limitation='One executor library overlay; fresh composed wheels remain required')
