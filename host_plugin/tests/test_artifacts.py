"""Independent archive boundary tests; no Docker daemon is required."""
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from openbexi_spell_host.container import Container


def archive(entries):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as output:
        for name, content in entries:
            info = tarfile.TarInfo(name)
            if content is None:
                info.type, info.linkname = tarfile.SYMTYPE, '../../escape'
                output.addfile(info)
            else:
                info.size = len(content)
                output.addfile(info, io.BytesIO(content))
    data.seek(0)
    return data


class ArtifactTests(unittest.TestCase):
    def test_changed_outputs_do_not_overwrite_project_and_ignored_inputs_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / 'procedure.py').write_bytes(b'original')
            (project / 'removed.txt').write_bytes(b'removed in snapshot')
            (project / '.env').write_bytes(b'private fixture')
            owned = Container(project)
            with owned.snapshot() as snapshot, tarfile.open(fileobj=snapshot) as contents:
                self.assertEqual(set(contents.getnames()), {'procedure.py', 'removed.txt'})
            result = owned.save_results(archive([('workspace/procedure.py', b'changed'),
                ('workspace/output.txt', b'42')]))
            self.assertEqual((project / 'procedure.py').read_bytes(), b'original')
            self.assertEqual((result / 'artifacts/procedure.py').read_bytes(), b'changed')
            self.assertEqual(json.loads((result / 'manifest.json').read_text())['deleted_in_snapshot'], ['removed.txt'])

    def test_malicious_paths_and_links_are_rejected(self):
        for name, content in [('workspace/../escape', b'x'), ('/absolute', b'x'),
                ('workspace/link', None), ('workspace/CON.txt', b'x'),
                ('workspace/stream:secret', b'x'), ('workspace/trailing.', b'x'),
                ('workspace/back\\slash', b'x')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    Container(directory).save_results(archive([(name, content)]))

    def test_duplicate_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                Container(directory).save_results(archive([('workspace/result', b'1'), ('workspace/result', b'2')]))


if __name__ == '__main__':
    unittest.main()
