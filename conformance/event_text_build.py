import hashlib,json,sys,sysconfig
from pathlib import Path
sys.path.insert(0,'/opt/event-text-patch')
from installed_provenance import capture_application
from event_text_patches import PREIMAGES,apply
out=Path('/opt/event-text-patch');site=Path(sysconfig.get_path('purelib'))
base=capture_application();(out/'base.json').write_text(json.dumps(base,indent=2)+'\n')
name,=PREIMAGES;path=site/name;before=path.read_bytes();after=apply(name,before)
(out/'original-rpc.py').write_bytes(before);(out/'patched-rpc.py').write_bytes(after);path.write_bytes(after)
sha=lambda b:hashlib.sha256(b).hexdigest()
(out/'build.json').write_text(json.dumps(dict(source=name,before_sha256=sha(before),after_sha256=sha(after),
 recipe_sha256=sha((out/'event_text_patches.py').read_bytes())),indent=2)+'\n')
