"""Compose independent retained memory and ranging source expectations."""
import hashlib
from pathlib import Path
from feature_source_donors import retained_raw
from library_source_donors import matching_recipe
from memory_complete_review import review
from ranging_source_donor import reopened_ground


def combined_ground(memory_overlay, ranging_overlay):
    name = 'openbexi_spell_dss/ground.py'
    before = (memory_overlay/'original'/name).read_bytes()
    after = (memory_overlay/'patched'/name).read_bytes()
    anchor = b"        if family == 'MEM':\n"
    assert before.count(anchor) == after.count(anchor) == 1
    prefix, suffix = before.split(anchor)
    assert after.startswith(prefix+anchor) and after.endswith(suffix)
    insertion = after[len(prefix+anchor):-len(suffix)]
    assert insertion == (b'            from .memory_images import prepare\n'
        b'            operation=prepare(self,method,request,settings,check)\n'
        b'            if operation is not None:return operation\n')
    ranging = reopened_ground(ranging_overlay)
    assert ranging.count(anchor) == 1
    return ranging.replace(anchor, anchor+insertion)


def apply(python, driver, composition, report, ranging_report):
    path, raw = retained_raw(report)
    overlay = Path(report['overlay'])
    proof = review(path, overlay, Path(report['telemetry_overlay']), Path(report['limit_overlay']),
                   report['source_revision'], report['runtime_image'])
    assert proof['checks'] == report['checks'] and len(proof['checks']) == 32
    recipe = composition.memory_feature_patches
    matching_recipe(report, raw, 'source_port/memory_feature_patches.py')
    manifest = raw['runtime_sources']['overlay']['manifest']
    assert set(manifest) == set(recipe.PREIMAGES)
    for name, row in manifest.items():
        output = python if name.startswith('spell/') else driver
        assert row['preimage_sha256'] == recipe.PREIMAGES[name]
        if name == 'openbexi_spell_dss/ground.py':
            ranging_overlay = Path(ranging_report['overlay'])
            assert output[name] == hashlib.sha256(reopened_ground(ranging_overlay)).hexdigest()
            output[name] = hashlib.sha256(combined_ground(overlay, ranging_overlay)).hexdigest()
        else:
            assert output[name] == row['preimage_sha256']
            output[name] = row['sha256']
    additions = raw['runtime_sources']['overlay']['added_sources']
    for name in additions:
        matching_recipe(report, raw, 'driver_plugin/src/'+name)
    return additions
