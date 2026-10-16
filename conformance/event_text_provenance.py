"""Explicit diagnostic overlay capture; never claim its source matches the base wheel."""
import hashlib,json,shutil,sysconfig
from pathlib import Path


def capture():
    folder=Path('/opt/event-text-patch')
    base=json.loads((folder/'base.json').read_bytes());change=json.loads((folder/'build.json').read_bytes())
    expected=dict(base['installed']);assert expected[change['source']]==change['before_sha256']
    expected[change['source']]=change['after_sha256']
    site=Path(sysconfig.get_path('purelib'))
    for name,digest in expected.items():
        assert hashlib.sha256((site/name).read_bytes()).hexdigest()==digest,name
    shutil.copytree(folder,Path('/workspace/event-text-overlay'))
    return base['integrated']
