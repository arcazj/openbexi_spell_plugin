"""Recompile and relink only the changed context graph in an owned dev image."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import zipfile

sys.path.insert(0, '/data-files-recipe')
from data_files_native_patches import NAME, apply

output = Path('/data-files-native')
output.mkdir()
sha = lambda content: hashlib.sha256(content).hexdigest()
archive = Path('/input/SPELL2.6.10-src.zip')
assert sha(archive.read_bytes()) == '2176e198f04c3f2ec99ee6f740871d9368997e3fd1e33d6734cb8e163cb6a0ed'
with zipfile.ZipFile(archive) as bundle:
    original = bundle.read(NAME)
path = Path('/source')/NAME
ported = path.read_bytes()
patched = apply(original, ported)
path.write_bytes(patched)
for prefix, content in [('original',original),('ported',ported),('patched',patched)]:
    target = output/prefix/NAME
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(content)
context = json.loads(Path('/out/context-build.json').read_text())['programs']['SPELL_Context']
flags = json.loads(Path('/out/native-build.json').read_text())['flags']
obj = output/'SPELLcontext.C.o'
compile_command = flags+['-c',str(path),'-o',str(obj)]
result = subprocess.run(compile_command,capture_output=True,text=True,timeout=180)
(output/'compile.log').write_text(result.stdout+result.stderr)
assert result.returncode == 0, result.stderr
objects = [str(obj) if row['unit'] == NAME else '/out/'+row['object'] for row in context['units']]
executable = output/'SPELL-Context'
link_command = ['c++','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
    *objects,'-L'+sysconfig.get_config_var('LIBDIR'),'-lpython3.13',
    '-llog4cplus','-lxerces-c','-lz','-lmenu','-lncurses','-o',str(executable)]
result = subprocess.run(link_command,capture_output=True,text=True,timeout=180)
(output/'link.log').write_text(result.stdout+result.stderr)
assert result.returncode == 0, result.stderr
shutil.copytree('/data-files-recipe',output/'recipe')
report = dict(upstream_sha256=sha(original),ported_sha256=sha(ported),patched_sha256=sha(patched),
    executable_sha256=sha(executable.read_bytes()),compile_command=compile_command,link_command=link_command,
    baseline_context_manifest_sha256=sha(Path('/out/context-build.json').read_bytes()),
    inherited_objects={row['unit']:sha((Path('/out')/row['object']).read_bytes()) for row in context['units'] if row['unit'] != NAME})
(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
