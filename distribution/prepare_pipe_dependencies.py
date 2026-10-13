"""Verify cached universal test wheels and write an exact CPython 3.13 lock."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'pytest':'8.4.2', 'iniconfig':'2.3.1', 'packaging':'26.3',
            'pluggy':'1.6.0', 'pygments':'2.21.0', 'colorama':'0.4.6'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    parser.add_argument('--download-log', type=Path, required=True)
    parser.add_argument('--offline-resolution', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    wheels = {}
    for path in sorted(args.wheelhouse.resolve().glob('*.whl')):
        with zipfile.ZipFile(path) as archive:
            metadata_name, = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            tags_name = metadata_name.rsplit('/',1)[0]+'/WHEEL'
            metadata = BytesParser().parsebytes(archive.read(metadata_name))
            tags = BytesParser().parsebytes(archive.read(tags_name)).get_all('Tag', [])
            if not tags or any(not tag.endswith('-none-any') for tag in tags):
                raise ValueError('Test wheel is not universal: '+path.name)
            name = canonicalize_name(metadata['Name'])
            if name in wheels or EXPECTED.get(name) != metadata['Version']:
                raise ValueError('Unexpected or duplicate dependency: '+name)
            if '3.13.15' not in SpecifierSet(metadata.get('Requires-Python','')):
                raise ValueError('Wheel excludes the declared CPython version: '+name)
            wheels[name] = dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size,
                version=metadata['Version'], requires_python=metadata.get('Requires-Python'),
                requires_dist=metadata.get_all('Requires-Dist', []), tags=tags)
    if set(wheels) != set(EXPECTED):
        raise ValueError('Incomplete pinned test dependency set')
    profiles = {}
    for system, os_name, sys_platform in [('Linux','posix','linux'),('Windows','nt','win32')]:
        environment = default_environment()
        environment.update(python_version='3.13', python_full_version='3.13.15',
            implementation_name='cpython', implementation_version='3.13.15',
            platform_python_implementation='CPython', platform_machine='x86_64',
            platform_system=system, os_name=os_name, sys_platform=sys_platform, extra='')
        pending, closure = ['pytest'], set()
        while pending:
            name = pending.pop()
            if name in closure:
                continue
            closure.add(name)
            for encoded in wheels[name]['requires_dist']:
                requirement = Requirement(encoded)
                if requirement.marker and not requirement.marker.evaluate(environment):
                    continue
                dependency = canonicalize_name(requirement.name)
                if dependency not in wheels or wheels[dependency]['version'] not in requirement.specifier:
                    raise ValueError('Dependency closure is unsatisfied: '+encoded)
                if requirement.extras or requirement.url:
                    raise ValueError('Unexpected external or extra dependency: '+encoded)
                pending.append(dependency)
        expected = set(EXPECTED)-({'colorama'} if system == 'Linux' else set())
        if closure != expected:
            raise ValueError('Declared dependency closure changed: '+system)
        profiles[system] = dict(environment=environment, packages=sorted(closure),
            metadata_closure_verified=True, installed_execution=False)
    lock = ROOT/'distribution/pipe-test-requirements.lock'
    lines = ['# CPython 3.13 FIFO/EOF qualification dependencies; all wheels are pure Python.',
             '# Generated from retained wheel METADATA; no runtime platform claim.']
    for name, row in sorted(wheels.items()):
        marker = ' ; sys_platform == "win32"' if name == 'colorama' else ''
        lines.append(f'{name}=={row["version"]}{marker} --hash=sha256:{row["sha256"]}')
    lock.write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
    result = dict(schema='openbexi.spell.pipe-test-dependencies/1', prepared=True,
        runtime_qualified=False, full_v06_accepted=False, python=sys.version,
        generator_sha256=sha(__file__), wheels=wheels, profiles=profiles,
        lock=dict(path=lock.relative_to(ROOT).as_posix(), sha256=sha(lock)),
        download_log=dict(path=str(args.download_log.resolve()), sha256=sha(args.download_log)),
        scope='Exact cached dependency bytes and Linux/Windows CPython 3.13 metadata closure only; installed pipe runs remain separate.')
    if args.offline_resolution:
        resolution = json.loads(args.offline_resolution.read_bytes())
        if resolution['environment']['sys_platform'] != 'win32':
            raise ValueError('Unexpected offline resolver platform')
        resolved = {canonicalize_name(row['metadata']['name']):row['metadata']['version'] for row in resolution['install']}
        if resolved != EXPECTED:
            raise ValueError('Offline resolver selected a different dependency set')
        for row in resolution['install']:
            name = canonicalize_name(row['metadata']['name'])
            if row['download_info']['archive_info']['hashes']['sha256'] != wheels[name]['sha256']:
                raise ValueError('Offline resolver selected different wheel bytes')
        result['offline_resolution'] = dict(path=str(args.offline_resolution.resolve()),
            sha256=sha(args.offline_resolution),platform='Windows',resolved=resolved,
            installed=False,linux_execution=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(output=str(args.output), sha256=sha(args.output), lock_sha256=sha(lock), wheels=len(wheels))))


if __name__ == '__main__':
    main()
