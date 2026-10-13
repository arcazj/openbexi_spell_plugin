"""Build/install two driver wheels offline and compare the complete wheel bytes.

This inexpensive preflight validates Python driver composition and packaging;
it does not replace native runtime behavior or the independent native rebuilds.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid

import build_images as builder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-image', required=True)
    parser.add_argument('--toolchain-id', required=True)
    parser.add_argument('--output', type=Path, default=builder.ROOT/'.qualification/v0.6/driver-preflight')
    args = parser.parse_args()
    evidence = args.output.resolve()/uuid.uuid4().hex
    snapshot = evidence/'source'
    snapshot.mkdir(parents=True, exist_ok=False)
    report = {'passed':False, 'full_v06_accepted':False,
              'network':'none', 'build_cache_enabled':False, 'toolchain':args.toolchain_id}
    try:
        shutil.copytree(builder.ROOT/'driver_plugin', snapshot/'driver_plugin',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc','build','*.egg-info'))
        site = snapshot/'driver_plugin/src'
        report['composition'] = builder.apply_driver_tree(site, site/'openbexi_dss_proxy/_composition')
        recipe = evidence/'driver-wheel.Dockerfile'
        recipe.write_text(builder.DRIVER_WHEEL_DOCKERFILE, encoding='utf-8', newline='\n')
        report['recipe_sha256'] = builder.sha(recipe)
        inputs = {p.relative_to(snapshot).as_posix():builder.sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}
        (evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n', encoding='utf-8', newline='\n')
        report['inputs_sha256'] = builder.sha(evidence/'inputs.json')
        report['wheels'] = []
        report['installed'] = []
        for label in ('a','b'):
            if builder.inspect(args.toolchain_image) != args.toolchain_id:
                raise ValueError('Frozen toolchain identity differs')
            builder.run(['docker','build','--no-cache','--network=none','--progress=plain',
                '--build-arg','TOOLCHAIN_IMAGE='+args.toolchain_image,'-f',recipe,
                '--output','type=local,dest='+str(evidence/label),snapshot], evidence/(label+'.log'))
            wheel, = (evidence/label/'wheels').glob('*.whl')
            report['wheels'].append(builder.inspect_wheel(wheel,require_driver_composition=True))
            installed_path = evidence/label/'driver-installed-record.json'
            installed = json.loads(installed_path.read_bytes())
            if installed['manifest'] != report['composition']:
                raise ValueError('Installed driver differs from its source composition')
            report['installed'].append({'sha256':builder.sha(installed_path),
                'record_files_verified':installed['record_files_verified']})
        if report['wheels'][0]['sha256'] != report['wheels'][1]['sha256']:
            raise ValueError('Independent driver wheel bytes differ')
        if inputs != {p.relative_to(snapshot).as_posix():builder.sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}:
            raise ValueError('Driver build snapshot changed')
        report['passed'] = True
    except Exception as error:
        report['error'] = type(error).__name__+': '+str(error)
    (evidence/'result.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'passed':report['passed'],'evidence':str(evidence),'error':report.get('error')},indent=2),flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
