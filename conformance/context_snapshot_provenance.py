"""Verify the explicit one-binary listener diagnostic overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path

RECIPES = {'context_snapshot_patches.py': 'source_port/context_snapshot_patches.py',
    'context_snapshot_build.py': 'conformance/context_snapshot_build.py',
    'context_snapshot_probe.py': 'conformance/context_snapshot_probe.py',
    'incremental_native.py': 'distribution/incremental_native.py'}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay = Path('/opt/context-snapshot-patch')
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
    return dict(baseline=base, context_snapshot_overlay=report)


def qualification_identity(record, inputs, normalized=None):
    from checkpoint_identity_provenance import qualification_identity as base_identity
    base = dict(record['baseline'], host_native_sha256=record['host_native_sha256'])
    identity = base_identity(base, inputs, normalized)
    overlay = record['context_snapshot_overlay']
    assert overlay['passed'] and not overlay['full_release_accepted']
    assert set(overlay['artifacts']) == set(overlay['original_artifacts']) == {'SPELL-Listener'}
    assert overlay['recipes'] == {name: inputs[path] for name, path in RECIPES.items()}
    for name, expected in overlay['original_artifacts'].items():
        assert expected == base['native_artifacts'][name] and overlay['artifacts'][name] != expected
    probes = overlay['probes']
    assert probes['passed'] and set(probes['probes']) == {'original','patched'}
    for label, probe in probes['probes'].items():
        assert probe['exit_code'] == (1 if label == 'original' else 0)
        assert probe['observation']['coherent'] is (label == 'patched')
        assert probe['observation']['subsequent_current'] and probe['observation']['unknown_context_rejected']
    return dict(kind='diagnostic-context-snapshot-overlay', baseline=identity, evidence=overlay,
        limitation='One listener binary overlay; fresh composed wheels remain required')
