"""Explicit diagnostic mailbox overlay; never fresh-wheel acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path

RECIPES = {
    'ipc_mailbox_patches.py': 'source_port/ipc_mailbox_patches.py',
    'ipc_mailbox_build.py': 'conformance/ipc_mailbox_build.py',
    'ipc_mailbox_race.cpp': 'conformance/ipc_mailbox_race.cpp',
    'incremental_native.py': 'distribution/incremental_native.py',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    overlay = Path('/opt/ipc-mailbox-patch')
    base = json.loads((overlay / 'baseline-installed.json').read_bytes())
    report = json.loads((overlay / 'manifest.json').read_bytes())
    root = Path(importlib.util.find_spec('spell_native').origin).parent
    assert sha(root / 'manifest.json') == base['manifest_sha256']
    for name, expected in base['python_sources'].items():
        assert sha(root.parent / name) == expected, name
    for name, expected in base['native_artifacts'].items():
        assert sha(root / 'bin' / name) == report['artifacts'].get(name, expected), name
    for label, field in [('original', 'preimage_sha256'), ('patched', 'patched_sha256')]:
        assert sha(overlay / label / 'source.C') == report[field]
    for name, expected in report['recipes'].items():
        assert sha(overlay / 'recipes' / name) == expected, name
    for name, probe in report['probes'].items():
        label, operation = name.split('-')
        assert sha(overlay / label / (operation + '.log')) == probe['log_sha256']
    return {'baseline': base, 'mailbox_overlay': report}


def qualification_identity(record, inputs, normalized=None):
    from checkpoint_identity_provenance import qualification_identity as base_identity
    base = dict(record['baseline'], host_native_sha256=record['host_native_sha256'])
    identity = base_identity(base, inputs, normalized)
    overlay = record['mailbox_overlay']
    if overlay['passed'] is not True or overlay['full_release_accepted'] is not False:
        raise ValueError('Mailbox overlay must be a passed diagnostic')
    if set(overlay['artifacts']) != {'libspell_executor313.so', 'SPELL-Context', 'SPELL-Listener'}:
        raise ValueError('Unexpected mailbox artifact set')
    if set(overlay['original_artifacts']) != set(overlay['artifacts']):
        raise ValueError('Mailbox baseline artifact set differs')
    for name, expected in overlay['original_artifacts'].items():
        if expected != base['native_artifacts'][name] or overlay['artifacts'][name] == expected:
            raise ValueError('Mailbox baseline artifact differs')
    if overlay['recipes'] != {name: inputs.get(path) for name, path in RECIPES.items()}:
        raise ValueError('Mailbox recipes differ from qualification input')
    if set(overlay['probes']) != {label + '-' + operation for label in ('original', 'patched')
                                for operation in ('place', 'cancel')}:
        raise ValueError('Missing original/fixed mailbox race controls')
    for name, probe in overlay['probes'].items():
        if (probe['exit_code'] == 0) != name.startswith('patched-'):
            raise ValueError('Mailbox differential control failed: ' + name)
    return dict(kind='diagnostic-mailbox-overlay', baseline=identity,
                native_artifacts=overlay['artifacts'], evidence=overlay,
                limitation='Original wheel RECORD retained; fresh composed rebuild required')
