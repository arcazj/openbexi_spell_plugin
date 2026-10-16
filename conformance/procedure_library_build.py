"""Reproduce the retained native library before changing its child resolver."""
import hashlib,json,shutil,subprocess,sys,sysconfig,zipfile
from pathlib import Path

INPUT=Path('/build-input');SOURCE=Path('/source');OUT=Path('/out')
EVIDENCE=Path('/opt/procedure-library-patch');SITE=Path(sysconfig.get_path('purelib'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sys.path[:0]=[str(INPUT/'source_port'),str(EVIDENCE)]
import native_patches
import procedure_library_patches as recipe
from installed_provenance import capture_application

EVIDENCE.mkdir(parents=True,exist_ok=True)
base=capture_application()
(EVIDENCE/'base.json').write_text(json.dumps(base,indent=2)+'\n')
donor=json.loads((INPUT/'donor/executor-build.json').read_bytes())
native=json.loads((INPUT/'donor/native-build.json').read_bytes())
assert donor['native_build_sha256']==sha(INPUT/'donor/native-build.json')
assert donor['runtime_sha256']==base['installed']['spell_native/bin/libspell_executor313.so']
archive=INPUT/'SPELL2.6.10-src.zip'
assert sha(archive)==native['archive_sha256']
SOURCE.mkdir();OUT.mkdir()
with zipfile.ZipFile(archive) as z:
    for member in z.infolist():
        target=(SOURCE/member.filename).resolve()
        assert target.is_relative_to(SOURCE)
        if member.is_dir():target.mkdir(parents=True,exist_ok=True)
        else:
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(member))
native_patches.apply_tree(SOURCE)
composition=INPUT/'donor/integrated-native'
manifest=json.loads((composition/'manifest.json').read_bytes())
assert manifest==native['composition']
for name,row in manifest['sources'].items():
    patch=composition/'patched'/name
    assert sha(patch)==row['patched_sha256']
    (SOURCE/name).write_bytes(patch.read_bytes())
extra={r['unit']:r for field in ('units','analysis_units','dta_units') for r in native[field]}
rows=donor['units']+[extra[n] for n in ('ws_filter.cpp','continuation.cpp')]
objects={}
for row in rows:
    assert row['exit_code']==0
    source=SOURCE/row['unit'] if row in donor['units'] else INPUT/'source_port/native'/row['unit']
    assert sha(source)==row['sha256'],str(source)
    original=INPUT/'donor'/row['object']
    objects[row['object']]=sha(original)
    shutil.copyfile(original,OUT/row['object'])
link=['c++','-shared','-pthread','-fsanitize=address,undefined','-Wl,--no-undefined',
    *[str(OUT/r['object']) for r in rows],'-L'+sysconfig.get_config_var('LIBDIR'),
    '-lpython3.13','-llog4cplus','-lxerces-c','-lz','-lmenu','-lncurses','-o',str(OUT/'libspell_executor313.so')]
def run(name,command):
    result=subprocess.run(command,capture_output=True,text=True)
    (EVIDENCE/(name+'.log')).write_text(result.stdout+result.stderr)
    assert result.returncode==0,name+': '+result.stderr
run('reproduce-original-library',link)
assert sha(OUT/'libspell_executor313.so')==donor['runtime_sha256'],'Retained objects do not reproduce the qualified library'
before=(SOURCE/recipe.SOURCE).read_bytes();after=recipe.apply(recipe.SOURCE,before)
(EVIDENCE/'original-child.C').write_bytes(before)
(EVIDENCE/'patched-child.C').write_bytes(after)
(SOURCE/recipe.SOURCE).write_bytes(after)
unit=next(r for r in donor['units'] if r['unit']==recipe.SOURCE)
compile_command=native['flags']+['-c',str(SOURCE/recipe.SOURCE),'-o',str(OUT/unit['object'])]
run('compile-child-resolver',compile_command)
run('link-child-resolver',link)
replacement=OUT/'libspell_executor313.so'
binary=SITE/'spell_native/bin/libspell_executor313.so'
shutil.copyfile(replacement,binary)
modules={}
for name in ('launcher.py','library.py'):
    source=INPUT/'source_port/distribution'/name
    target=SITE/'spell_native'/name
    if name=='launcher.py':assert sha(target)==base['installed']['spell_native/launcher.py']
    else:assert not target.exists()
    shutil.copyfile(source,target)
    modules['spell_native/'+name]=sha(source)
    shutil.copyfile(source,EVIDENCE/name)
record=dict(passed=True,diagnostic_only=True,donor_runtime_sha256=donor['runtime_sha256'],
    runtime_sha256=sha(binary),original_link_reproduced=True,object_inputs=objects,
    compile_command=compile_command,link_command=link,modules=modules,
    donor_executor_report_sha256=sha(INPUT/'donor/executor-build.json'),
    native_recipe_sha256=sha(INPUT/'source_port/native_patches.py'),
    recipe_sha256=sha(EVIDENCE/'procedure_library_patches.py'),
    original_child_sha256=sha(EVIDENCE/'original-child.C'),patched_child_sha256=sha(EVIDENCE/'patched-child.C'))
(EVIDENCE/'build.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
