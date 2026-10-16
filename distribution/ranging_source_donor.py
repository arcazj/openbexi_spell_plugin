"""Adopt ranging bytes only from the independently reviewed native capture."""
from pathlib import Path
from feature_source_donors import retained_raw
from library_source_donors import matching_recipe
from ranging_complete_review import review
import hashlib


def apply(python,driver,composition,report):
    path,raw=retained_raw(report)
    proof=review(path,Path(report['overlay']),report['source_revision'],report['runtime_image'])
    assert proof['checks']==report['checks'] and len(proof['checks'])==20
    recipe=composition.ranging_complete_patches
    matching_recipe(report,raw,'source_port/ranging_complete_patches.py')
    manifest=raw['runtime_sources']['overlay']['manifest']
    assert set(manifest)==set(recipe.PREIMAGES)
    for name,row in manifest.items():
        output=python if name.startswith('spell/') else driver
        assert output[name]==row['preimage_sha256']==recipe.PREIMAGES[name]
        output[name]=row['sha256']
    additions=raw['runtime_sources']['overlay']['added_sources']
    for name in additions:matching_recipe(report,raw,'driver_plugin/src/'+name)
    # Expected reopen bytes are derived from the retained native donor and one
    # literal, independently reviewed guard. The combined native regression is
    # still required; these expectations alone never qualify a runtime.
    name='openbexi_spell_dss/ground.py'
    raw=(Path(report['overlay'])/'patched'/name).read_bytes()
    lines=raw.splitlines(keepends=True)
    indices=[i for i,line in enumerate(lines) if line==b'            initialize(state)\n']
    assert len(indices)==1
    i=indices[0]+1
    assert lines[i]==b"            journal.db.execute('UPDATE ground SET state=? WHERE namespace=?',(canonical(state),self.namespace))\n"
    lines[i:i+1]=[b'            if state != json.loads(encoded):\n',b'    '+lines[i]]
    assert driver[name]==hashlib.sha256(raw).hexdigest()
    driver[name]=hashlib.sha256(b''.join(lines)).hexdigest()
    return additions
