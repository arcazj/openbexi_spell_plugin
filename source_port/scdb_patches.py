"""Configured SCDB read-only view over the original database backend.

SPDX-License-Identifier: LGPL-3.0-or-later
Only the named runtime SCDB object is protected. This is a language object
policy, not an operating-system permission policy for aliases to its file.
"""
import hashlib
import json
from pathlib import Path
import zipfile

ARCHIVE_SHA256 = '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
PREIMAGES = {
    'spell/lib/adapter/databases/database.py':'f1913ae35258bc177711b9a33645f4867627e3d32087eac107bc801da4b07b0e',
    'spell/lib/adapter/dbmgr.py':'c1852dffb2e4ef363ca2b779dd5f7778c46ca81bc13204e0d9a71b2712d50188',
}

VIEW = '''

class ReadOnlyDatabase(Database):
    """Read-only public database API backed by the configured original reader.

    Returned data are detached snapshots. Refresh builds another real reader
    and publishes it only after success, so failed I/O cannot expose partial
    or empty state. GDB and user databases never use this view.
    """
    def __init__(self, backend, name, path, extension):
        super(ReadOnlyDatabase, self).__init__()
        self.__backend = backend
        self.__backend_type = type(backend)
        self.__backend_args = (name, path, extension)

    def __getitem__(self, key):
        from copy import deepcopy
        return deepcopy(self.__backend[key])

    def get(self, key):
        from copy import deepcopy
        return deepcopy(self.__backend.get(key))

    def keys(self):
        return list(self.__backend.keys())

    def has_key(self, key):
        return self.__backend.has_key(key)

    def __len__(self):
        return len(self.__backend)

    def __bool__(self):
        return bool(self.__backend)

    def __repr__(self):
        return repr(self.__backend)

    def id(self):
        return self.__backend.id()

    def __refresh(self, reload):
        candidate = self.__backend_type(*self.__backend_args)
        try:
            result = candidate.reload() if reload else candidate.load()
        except DriverException:
            raise
        except Exception as error:
            raise DriverException('Cannot refresh read-only database', str(error)) from error
        self.__backend = candidate
        return result

    def load(self):
        return self.__refresh(False)

    def reload(self):
        return self.__refresh(True)

    def _reject_write(self):
        raise DriverException('Database is read-only', self.__backend_args[0])

    def __setitem__(self, key, value):
        self._reject_write()

    def __delitem__(self, key):
        self._reject_write()

    def set(self, key, value, format=None):
        self._reject_write()

    def create(self):
        self._reject_write()

    def commit(self):
        self._reject_write()
'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def apply(name, raw):
    if name not in PREIMAGES or digest(raw) != PREIMAGES[name]:
        raise ValueError('Unexpected SCDB preimage: '+name)
    if name.endswith('/database.py'):
        result = raw + VIEW.encode()
    else:
        old = b'        self.__databases[dbName] = db\n'
        assert raw.count(old) == 1
        result = raw.replace(old, b'''        # LRM p79: the automatically installed SCDB object is read-only.
        # Preserve all original configured backend construction and loading.
        if dbName == 'SCDB':
            db = ReadOnlyDatabase(db, dbName, dbPath, dbExt)
''' + old)
    compile(result, name, 'exec')
    return result


def apply_tree(site, archive, output):
    site, archive, output = Path(site), Path(archive), Path(output)
    assert digest(archive.read_bytes()) == ARCHIVE_SHA256
    with zipfile.ZipFile(archive) as bundle:
        originals = {name:bundle.read('src/spell/'+name) for name in PREIMAGES}
    ported = {name:(site/name).read_bytes() for name in PREIMAGES}
    patched = {}
    for name in PREIMAGES:
        assert digest(originals[name]) == PREIMAGES[name]
        patched[name] = apply(name, ported[name])
    output.mkdir(parents=True, exist_ok=False)
    sources = {}
    for name in PREIMAGES:
        sources[name] = {}
        for label, contents in (('original',originals),('ported',ported),('patched',patched)):
            path = output/label/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(contents[name])
            sources[name][label+'_sha256'] = digest(contents[name])
        (site/name).write_bytes(patched[name])
    recipe = Path(__file__).read_bytes()
    (output/'scdb_patches.py').write_bytes(recipe)
    report = dict(schema='openbexi.spell.scdb-overlay/1', sources=sources,
        archive_sha256=ARCHIVE_SHA256, recipe_sha256=digest(recipe),
        limitation='Diagnostic overlay; fresh composed wheel with complete RECORD is required for distribution acceptance.')
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report
