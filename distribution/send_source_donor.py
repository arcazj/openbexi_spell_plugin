"""Adopt Send source bytes from independently reviewed native evidence."""
from pathlib import Path
from feature_source_donors import retained_raw
from library_source_donors import matching_recipe
from send_complete_review import review


def apply(python,composition,report):
    path,raw=retained_raw(report)
    actual=review(path,Path(report['overlay']),Path(report['telemetry_overlay']),Path(report['limit_overlay']),
                  report['source_revision'],report['runtime_image'])
    assert actual['checks']==report['checks'] and len(actual['checks'])==12
    matching_recipe(report,raw,'source_port/send_complete_patches.py')
    recipe=composition.send_complete_patches
    manifest=raw['runtime_sources']['overlay']['manifest']
    assert set(manifest)==set(recipe.PREIMAGES)
    for name,row in manifest.items():
        assert python[name]==row['preimage_sha256']==recipe.PREIMAGES[name]
        python[name]=row['sha256']
