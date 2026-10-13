"""Provenance parser unit checks; these do not claim runtime conformance."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
sys.path.insert(0,str(ROOT/'source_port'))
from checkpoint_error_provenance import qualification_identity
from installed_provenance import PROFILE
import checkpoint_error_patches as patch
import native_patches


class IdentityChecks(unittest.TestCase):
    def setUp(self):
        with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as bundle:
            original=bundle.read(patch.SOURCE)
        ported=native_patches.apply(patch.SOURCE,original)
        corrected=patch.apply(patch.SOURCE,original,ported,fix=True)
        hashes={label+'_sha256':hashlib.sha256(raw).hexdigest() for label,raw in
            [('original',original),('ported',ported),('patched',corrected)]}
        digest=hashlib.sha256((ROOT/'source_port/checkpoint_error_patches.py').read_bytes()).hexdigest()
        # Deliberately minimal parser fixture. Actual capture() validates files,
        # complete manifests, recipes, and artifacts before this function runs.
        self.record=dict(profile=PROFILE,manifest_sha256='fixture-manifest',python_sources={},
            native_artifacts={'libspell_executor313.so':'fixture-artifact'},
            manifest={'composition':{'native':{'sources':{patch.SOURCE:hashes},
                'recipes':{'checkpoint_error_patches.py':{'sha256':digest,'lf_sha256':digest}}}}})
        self.inputs={'source_port/checkpoint_error_patches.py':digest}

    def test_core_and_extra_bound_host_evidence_have_same_identity(self):
        expected=qualification_identity(self.record,self.inputs)
        record=copy.deepcopy(self.record);record['host_native_sha256']='fixture-host'
        self.inputs['host_runtime/python/native.py']='fixture-host'
        self.assertEqual(qualification_identity(record,self.inputs),expected)
        self.inputs['host_runtime/python/native.py']='wrong'
        with self.assertRaises(ValueError):qualification_identity(record,self.inputs)

    def test_missing_and_wrong_native_unit_rejected(self):
        for replacement in (None,{'original_sha256':'wrong','ported_sha256':'wrong','patched_sha256':'wrong'}):
            with self.subTest(replacement=replacement):
                record=copy.deepcopy(self.record)
                sources=record['manifest']['composition']['native']['sources']
                if replacement is None:del sources[patch.SOURCE]
                else:sources[patch.SOURCE]=replacement
                with self.assertRaises(ValueError):qualification_identity(record,self.inputs)

    def test_missing_recipe_rejected(self):
        self.record['manifest']['composition']['native']['recipes'].clear()
        with self.assertRaises(ValueError):qualification_identity(self.record,self.inputs)

    def test_different_qualification_source_rejected(self):
        self.inputs['source_port/checkpoint_error_patches.py']='wrong'
        with self.assertRaises(ValueError):qualification_identity(self.record,self.inputs)

    def test_missing_runtime_rejected(self):
        with self.assertRaises(ValueError):qualification_identity({},self.inputs)


if __name__=='__main__':unittest.main()
