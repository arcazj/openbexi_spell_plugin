"""Exact source identity is required before the cancellation correction applies."""
import hashlib
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source_port'))
import native_patches
import shutdown_pause_patches as patch


class ShutdownPauseRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ROOT / 'docs/reference/SPELL2.6.10-src.zip') as archive:
            cls.original = archive.read(patch.SOURCE)
        cls.ported = native_patches.apply(patch.SOURCE, cls.original)

    def test_exact_original_and_ported_preimages(self):
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), patch.ORIGINAL)
        self.assertEqual(hashlib.sha256(self.ported).hexdigest(), patch.PORTED)
        result = patch.apply(patch.SOURCE, self.original, self.ported)
        self.assertEqual(hashlib.sha256(result).hexdigest(),
                         'fa847a22bd88e970b1ae17f523c2c53b492f0722f0449eb232897ff24a1e6e33')
        self.assertEqual(result.replace(patch.AFTER.encode(), patch.BEFORE.encode()), self.ported)

    def test_changed_original_rejected(self):
        with self.assertRaises(ValueError):
            patch.apply(patch.SOURCE, self.original + b'\n', self.ported)

    def test_changed_port_rejected(self):
        with self.assertRaises(ValueError):
            patch.apply(patch.SOURCE, self.original, self.ported + b'\n')

    def test_wrong_unit_rejected(self):
        with self.assertRaises(ValueError):
            patch.apply('lib/SPELL_EXC/src/SPELLexecutor.C', self.original, self.ported)


if __name__ == '__main__':
    unittest.main()
