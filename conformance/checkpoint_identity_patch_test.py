"""Checked-source composition tests; no native behavior claim."""
import hashlib
from pathlib import Path
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source_port'))
import native_patches
import data_files_native_patches
import checkpoint_identity_patches
import checkpoint_context_patches


class CheckedSourceTests(unittest.TestCase):
    def sources(self,patch):
        with zipfile.ZipFile(ROOT/'docs/reference/SPELL2.6.10-src.zip') as bundle:
            original=bundle.read(patch.SOURCE)
        ported=native_patches.apply(patch.SOURCE,original)
        if patch is checkpoint_context_patches:
            ported=data_files_native_patches.apply(original,ported)
        return original,ported

    def test_exact_original_composition_and_mutated_preimages(self):
        for patch in (checkpoint_identity_patches,checkpoint_context_patches):
            with self.subTest(source=patch.SOURCE):
                original,ported=self.sources(patch)
                result=patch.apply(patch.SOURCE,original,ported)
                self.assertNotEqual(result,ported)
                for name,upstream,composed in ((patch.SOURCE,original+b' ',ported),
                        (patch.SOURCE,original,ported+b' '),('wrong',original,ported),
                        (patch.SOURCE,original,result)):
                    with self.assertRaises((AssertionError,ValueError)):
                        patch.apply(name,upstream,composed)

    def test_preserves_asrun_validation_and_instance_checkpoint_names(self):
        original,ported=self.sources(checkpoint_context_patches)
        patched=checkpoint_context_patches.apply(checkpoint_context_patches.SOURCE,original,ported)
        marker=b'\n\tfiles = SPELLutils::getFilesInDir(arDataDir);'
        self.assertEqual(ported.split(marker,1)[1],patched.split(marker,1)[1])
        original,ported=self.sources(checkpoint_identity_patches)
        patched=checkpoint_identity_patches.apply(checkpoint_identity_patches.SOURCE,original,ported)
        old=b'        startup.procedureFile = m_procedure;'
        start=ported.index(old)
        suffix=ported[start+len(old):]
        self.assertTrue(patched.endswith(suffix))
        self.assertTrue(patched.startswith(ported[:start]))


if __name__=='__main__':unittest.main()
