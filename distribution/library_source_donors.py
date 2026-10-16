"""Take manoeuvre and native resolver expectations only from reviewed captures."""
import hashlib
from pathlib import Path
import sys
from evidence_sources import source_bytes

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
from manoeuvre_database_review import review as manoeuvre_review
from procedure_library_review import review as procedure_review
from feature_source_donors import retained_raw


def matching_recipe(report,raw,path):
    frozen=source_bytes(ROOT,path,report['source_revision'])
    assert hashlib.sha256(frozen).hexdigest()==raw['inputs'][path]
    assert frozen.replace(b'\r\n',b'\n')==(ROOT/path).read_bytes().replace(b'\r\n',b'\n')


def apply(python,native,composition,reports):
    for key,review in (('manoeuvre',manoeuvre_review),('procedure_library',procedure_review)):
        report=reports[key];path,raw=retained_raw(report)
        fresh=review(path,Path(report['overlay']),report['source_revision'],report['runtime_image'])
        assert fresh['checks']==report['checks']
        if key=='manoeuvre':
            assert len(raw['checks'])==8
            recipe=composition.manoeuvre_database_patches
            matching_recipe(report,raw,'source_port/manoeuvre_database_patches.py')
            manifest=raw['runtime_sources']['overlay']['manifest']
            assert set(manifest)==set(recipe.PREIMAGES)
            for name,row in manifest.items():
                assert python[name]==recipe.PREIMAGES[name]==row['preimage_sha256']
                python[name]=row['sha256']
        else:
            assert len(raw['checks'])==12
            recipe=composition.procedure_library_patches
            matching_recipe(report,raw,'source_port/procedure_library_patches.py')
            record=raw['runtime_sources']['overlay']['build']
            assert native[recipe.SOURCE]['patched']==recipe.PREIMAGES[recipe.SOURCE]==record['original_child_sha256']
            native[recipe.SOURCE]['patched']=record['patched_child_sha256']
            modules={}
            for name,digest in record['modules'].items():
                path='source_port/distribution/'+Path(name).name
                matching_recipe(report,raw,path)
                assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
                modules[path]=digest
    return modules
