"""Verify a limit overlay against a complete, RECORD-checked composed image."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SITE = Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE = Path('/opt/limit-features-patch')
ADDED = (
    'openbexi_spell_dss/limit_definitions.py', 'openbexi_spell_dss/limit_algorithm.py',
    'openbexi_spell_dss/limits.py', 'openbexi_spell_dss/limit_files/normal.json',
    'openbexi_dss_proxy/limit_arguments.py', 'openbexi_dss_proxy/limit_profile.py',
)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {path.relative_to(SITE).as_posix(): digest(path)
        for package in ('spell', 'spell_native', 'openbexi_dss_proxy', 'openbexi_spell_dss')
        for path in (SITE/package).rglob('*') if path.is_file()
        and (path.suffix in ('.py', '.so') or path.parent.name in ('bin', 'limit_files'))}


def capture():
    base = json.loads((EVIDENCE/'base.json').read_bytes())
    if base['profile'] != 'fresh-composed-display-command-wheel/1':
        raise ValueError('Limit overlay requires a fresh composed base')
    expected = dict(base['installed'])
    manifest = json.loads((EVIDENCE/'manifest.json').read_bytes())
    spec = importlib.util.spec_from_file_location('limit_feature_recipe', EVIDENCE/'limit_feature_patches.py')
    recipe = importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    if set(manifest) != set(recipe.PREIMAGES):raise ValueError('Incomplete limit overlay')
    for name, row in manifest.items():
        original, patched = EVIDENCE/'original'/name, EVIDENCE/'patched'/name
        if expected.get(name) != row['preimage_sha256'] or digest(original) != row['preimage_sha256']:
            raise ValueError('Limit preimage differs: '+name)
        if recipe.apply(name, original.read_bytes()) != patched.read_bytes() or digest(patched) != row['sha256']:
            raise ValueError('Limit recipe replay differs: '+name)
        expected[name] = row['sha256']
    additions = {}
    for name in ADDED:
        if name in expected:raise ValueError('Limit addition replaces base source')
        expected[name] = additions[name] = digest(EVIDENCE/'modules'/name)
    actual = sources()
    if actual != expected:raise ValueError('Undeclared limit application changes: '+repr(
        sorted(name for name in set(actual)|set(expected) if actual.get(name) != expected.get(name))))
    return dict(profile='fresh-composed-wheel-plus-limit-overlay/1', integrated=base['integrated'],
        installed=actual, base_sha256=digest(EVIDENCE/'base.json'), base_profile=base['profile'],
        overlay=dict(manifest=manifest, added_sources=additions, files={
            path.relative_to(EVIDENCE).as_posix(): digest(path) for path in EVIDENCE.rglob('*')
            if path.is_file() and path.name != 'base.json' and '__pycache__' not in path.parts}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--freeze-base']:
        from installed_provenance import capture_application
        target = EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace frozen limit base')
        target.write_text(json.dumps(capture_application(), indent=2)+'\n')
    else:print(json.dumps(capture(), indent=2))
