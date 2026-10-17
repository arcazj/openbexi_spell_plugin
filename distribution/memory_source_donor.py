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


def apply(python, driver, composition, report, ranging_report, final_report=None):
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
        import sequence_memory_successor as successor
        source = 'driver_plugin/src/'+name
        if final_report is not None and name == successor.SOURCE:
            from evidence_sources import source_bytes
            from library_source_donors import ROOT
            before = source_bytes(ROOT, source, report['source_revision'])
            before_hash = hashlib.sha256(before).hexdigest()
            assert before_hash == raw['inputs'][source] == additions[name]
            after = successor.apply(before)
            assert after == (ROOT/source).read_bytes()
            after_hash = hashlib.sha256(after).hexdigest()
            assert final_report['direct_source_changes'] == [dict(source=name,
                before_sha256=before_hash, after_sha256=after_hash,
                replay='distribution/sequence_memory_successor.py')]
            assert final_report['driver_additions'][name] == after_hash
        else:
            matching_recipe(report, raw, source)
    return additions
