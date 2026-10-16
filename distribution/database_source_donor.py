"""Adopt database source hashes from all independently reviewed native cases."""
from pathlib import Path
import json
from database_format_review import read,ref,review
from library_source_donors import matching_recipe


def apply(python,composition,report):
    paths={key:Path(row['path']) for key,row in report['raw'].items()}
    assert all(ref(path)==report['raw'][key] for key,path in paths.items())
    actual=review(paths,Path(report['overlay']),Path(report['telemetry_overlay']),Path(report['limit_overlay']),
                  report['source_revision'],report['runtime_image'])
    assert json.dumps(actual['checks'],sort_keys=True)==json.dumps(report['checks'],sort_keys=True) and len(actual['checks'])==52
    raw=read(paths['formats'])
    matching_recipe(report,raw,'source_port/database_format_patches.py')
    recipe=composition.database_format_patches
    manifest=raw['runtime_sources']['overlay']['manifest']
    assert set(manifest)==set(recipe.PREIMAGES)
    for name,row in manifest.items():
        assert python[name]==row['preimage_sha256']==recipe.PREIMAGES[name]
        python[name]=row['sha256']
