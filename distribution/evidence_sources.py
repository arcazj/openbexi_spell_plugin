"""Read current qualification inputs or an explicitly frozen diagnostic revision."""
from functools import lru_cache
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
