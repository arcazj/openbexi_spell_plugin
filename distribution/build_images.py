"""Build fresh offline host/DSS images from an explicitly selected native wheel.

Every invocation retains a unique source snapshot, fresh driver wheel, image
identities, logs and installed RECORD checks. This is not release acceptance.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source_port'))
from integrated_patches import recipe_hashes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(tag):
    return subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()


def run(command, log):
    print('Running '+' '.join(map(str,command)), flush=True)
    with log.open('w', encoding='utf-8', newline='\n') as output:
        result = subprocess.run(list(map(str,command)), cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Command exited {result.returncode}; evidence: {log}')


def inspect_wheel(wheel, require_composition=False):
    with zipfile.ZipFile(wheel) as archive:
        record, = [name for name in archive.namelist() if name.endswith('.dist-info/RECORD')]
        rows = list(csv.reader(io.StringIO(archive.read(record).decode())))
        if len(rows) != len(archive.namelist()) or {row[0] for row in rows} != set(archive.namelist()):
            raise ValueError('Wheel RECORD does not cover exactly its files')
        for name, expected, size in rows:
            if name == record:
                if (expected,size) != ('',''):
                    raise ValueError('Unexpected wheel RECORD self-hash')
                continue
            content = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
            if expected != 'sha256='+encoded or int(size) != len(content):
                raise ValueError('Wheel RECORD mismatch: '+name)
        report = {'name':wheel.name,'sha256':sha(wheel),'record_files_verified':len(rows)-1}
        if require_composition:
            manifest = json.loads(archive.read('spell_native/manifest.json'))
            if set(manifest.get('composition',{})) != {'native','python'}:
                raise ValueError('Selected wheel lacks the complete native/Python composition')
            for name, expected in manifest['native_artifacts'].items():
                if hashlib.sha256(archive.read('spell_native/bin/'+name)).hexdigest() != expected:
                    raise ValueError('Selected wheel native manifest mismatch: '+name)
            for name, expected in manifest['python_sources'].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError('Selected wheel Python manifest mismatch: '+name)
            for kind, composition in manifest['composition'].items():
                if composition['recipes'] != recipe_hashes():
                    raise ValueError('Selected wheel predates the current composed recipes: '+kind)
            report['native_artifacts'] = manifest['native_artifacts']
            report['composition'] = manifest['composition']
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-wheel',type=Path,required=True)
    parser.add_argument('--toolchain-image',required=True)
    parser.add_argument('--toolchain-id',required=True,help='Expected sha256 identity of the retained complete toolchain')
    parser.add_argument('--output',type=Path,default=ROOT/'.qualification/v0.6/images')
    options = parser.parse_args()
    run_id = uuid.uuid4().hex
    evidence = options.output.resolve()/run_id
    snapshot = evidence/'source'
    snapshot.mkdir(parents=True,exist_ok=False)
    report = {'passed':False,'run_id':run_id,'v06_release_accepted':False,
              'network':'none','build_cache_enabled':False}
    try:
        toolchain = inspect(options.toolchain_image)
        if toolchain != options.toolchain_id:
            raise ValueError('Frozen toolchain image differs from the requested identity')
        report['toolchain'] = toolchain
        for name in ('host_runtime','driver_plugin'):
            shutil.copytree(ROOT/name,snapshot/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','build','*.egg-info'))
        (snapshot/'distribution').mkdir()
        for name in ('build_images.py','verify_image.py'):
            shutil.copyfile(ROOT/'distribution'/name,snapshot/'distribution'/name)
        wheels = snapshot/'.runtime-input'
        (wheels/'native').mkdir(parents=True)
        (wheels/'driver').mkdir()
        selected = options.native_wheel.resolve()
        report['native_wheel'] = inspect_wheel(selected,require_composition=True)
        shutil.copyfile(selected,wheels/'native'/selected.name)
        # Docker context transfer avoids host bind-mount requirements and keeps
        # compiler-generated wheel metadata outside the source checkout.
        driver_recipe = evidence/'driver-wheel.Dockerfile'
        driver_recipe.write_text('''ARG TOOLCHAIN_IMAGE
FROM ${TOOLCHAIN_IMAGE} AS driver
COPY driver_plugin /driver
RUN python -m pip wheel --no-index --no-build-isolation --no-deps --wheel-dir=/wheels /driver
FROM scratch
COPY --from=driver /wheels /wheels
''',encoding='utf-8',newline='\n')
        run(['docker','build','--no-cache','--network=none','--progress=plain',
             '--build-arg','TOOLCHAIN_IMAGE='+options.toolchain_image,'-f',driver_recipe,
             '--output','type=local,dest='+str(evidence/'driver-package'),snapshot],evidence/'driver-wheel.log')
        built_driver, = (evidence/'driver-package/wheels').glob('*.whl')
        shutil.copyfile(built_driver,wheels/'driver'/built_driver.name)
        report['driver_wheel_recipe_sha256'] = sha(driver_recipe)
        driver, = (wheels/'driver').glob('*.whl')
        report['driver_wheel'] = inspect_wheel(driver)
        inputs = {p.relative_to(snapshot).as_posix():sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}
        (evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n',encoding='utf-8',newline='\n')
        report['inputs_sha256'] = sha(evidence/'inputs.json')
        host_tag = 'openbexi-spell-host:v06-integrated-'+run_id[:12]
        dss_tag = 'openbexi-spell-dss:v06-integrated-'+run_id[:12]
        for component, tag, argument in (
            ('host_runtime',host_tag,'TOOLCHAIN_IMAGE='+options.toolchain_image),
            ('driver_plugin',dss_tag,'HOST_IMAGE='+host_tag)):
            if inspect(options.toolchain_image) != toolchain:
                raise ValueError('Frozen toolchain changed during image construction')
            run(['docker','build','--no-cache','--network=none','--progress=plain',
                 '--build-arg',argument,'-f',snapshot/component/'Dockerfile','-t',tag,snapshot],
                evidence/(component+'-build.log'))
            report[component] = {'tag':tag,'image':inspect(tag)}
        if inputs != {p.relative_to(snapshot).as_posix():sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}:
            raise ValueError('Image source snapshot changed during build')
        run(['docker','run','--rm','--network=none','--entrypoint','python',
             report['driver_plugin']['image'],'-I','-c',
             (snapshot/'distribution/verify_image.py').read_text(encoding='utf-8')],evidence/'installed-record.json')
        installed = json.loads((evidence/'installed-record.json').read_text())
        if not installed['passed'] or installed['native_artifacts'] != report['native_wheel']['native_artifacts']:
            raise ValueError('Installed native payload differs from the selected wheel')
        report['installed_record_sha256'] = sha(evidence/'installed-record.json')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    (evidence/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'passed':report['passed'],'evidence':str(evidence),'error':report.get('error')},indent=2),flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
