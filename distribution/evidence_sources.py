"""Read current qualification inputs or an explicitly frozen diagnostic revision."""
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import subprocess


@lru_cache(maxsize=2048)
def _committed(root, revision, name):
    # Only immutable full object identities are cached; working files never are.
    return subprocess.check_output(['git', 'show', revision + ':' + name], cwd=root)


def source_bytes(root, name, revision=None):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Qualification source escapes repository: ' + name)
    if revision is None:
        return path.read_bytes()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Historical evidence requires a full immutable commit identity')
    return _committed(str(root), revision, path.relative_to(root).as_posix())


def host_source_hashes(root, revision=None):
    """Keep historical host evidence bound to its explicitly frozen sources."""
    root = Path(root).resolve()
    prefix = 'host_runtime/python/'
    if revision is None:
        names = [p.relative_to(root).as_posix() for p in (root/prefix).glob('*.py')]
    else:
        if not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('Historical evidence requires a full immutable commit identity')
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', revision,
                                         '--', prefix], cwd=root, text=True).splitlines()
        names = [name for name in names if Path(name).parent.as_posix() == prefix.rstrip('/')
                 and name.endswith('.py')]
    if not names:
        raise ValueError('Qualification revision has no host sources')
    return {Path(name).name: hashlib.sha256(source_bytes(root, name, revision)).hexdigest()
            for name in names}
