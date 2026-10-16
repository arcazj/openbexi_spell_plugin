"""Verify telemetry deadlines over the frozen, independently recorded limit overlay."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SITE = Path('/usr/local/lib/python3.13/site-packages')
EVIDENCE = Path('/opt/telemetry-features-patch')
ADDED = ('openbexi_spell_dss/telemetry_budget.py',)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {path.relative_to(SITE).as_posix(): digest(path)
        for package in ('spell', 'spell_native', 'openbexi_dss_proxy', 'openbexi_spell_dss')
        for path in (SITE/package).rglob('*') if path.is_file()
        and (path.suffix in ('.py', '.so') or path.parent.name in ('bin', 'limit_files'))}


def capture():
    if not EVIDENCE.exists():
        from installed_provenance import capture_application
        application = capture_application()
        recipes = application['integrated']['manifest']['composition']['native']['recipes']
        if not {'limit_feature_patches.py','telemetry_feature_patches.py'} <= set(recipes):
            raise ValueError('Composed telemetry candidate lacks its required recipes')
        return dict(application,profile='fresh-composed-limit-telemetry-wheel/1')
    base = json.loads((EVIDENCE/'base.json').read_bytes())
    if base['profile'] != 'fresh-composed-wheel-plus-limit-overlay/1':
        raise ValueError('Limit overlay requires a fresh composed base')
    expected = dict(base['installed'])
    manifest = json.loads((EVIDENCE/'manifest.json').read_bytes())
    spec = importlib.util.spec_from_file_location('telemetry_feature_recipe', EVIDENCE/'telemetry_feature_patches.py')
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
    for name, expected_hash in base['overlay']['files'].items():
        if digest(Path('/opt/limit-features-patch')/name)!=expected_hash:
            raise ValueError('Frozen limit evidence changed: '+name)
    if digest(Path('/opt/limit-features-patch/base.json'))!=base['base_sha256']:
        raise ValueError('Frozen limit base identity changed')
    actual = sources()
    if actual != expected:raise ValueError('Undeclared limit application changes: '+repr(
        sorted(name for name in set(actual)|set(expected) if actual.get(name) != expected.get(name))))
    return dict(profile='fresh-composed-limit-telemetry-overlays/1', integrated=base['integrated'],
        installed=actual, base_sha256=digest(EVIDENCE/'base.json'), base_profile=base['profile'],
        overlay=dict(manifest=manifest, added_sources=additions, files={
            path.relative_to(EVIDENCE).as_posix(): digest(path) for path in EVIDENCE.rglob('*')
            if path.is_file() and path.name != 'base.json' and '__pycache__' not in path.parts}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--freeze-base']:
        sys.path.insert(0,'/opt/limit-features-patch')
        from limit_features_provenance import capture as capture_application
        target = EVIDENCE/'base.json'
        if target.exists():raise ValueError('Refusing to replace frozen limit base')
        target.write_text(json.dumps(capture_application(), indent=2)+'\n')
    else:print(json.dumps(capture(), indent=2))
