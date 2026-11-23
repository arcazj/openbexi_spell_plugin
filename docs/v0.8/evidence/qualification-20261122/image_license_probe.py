"""Inventory license metadata and notice hashes in the current isolated Linux image."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def debian_notices():
    packages = {}
    listing = subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'], text=True)
    for line in listing.splitlines():
        qualified, version = line.split('\t')
        name = qualified.split(':')[0]
        notice = Path('/usr/share/doc') / name / 'copyright'
        if notice.is_file():
            packages[name] = {'version': version, 'file': str(notice), 'sha256': checksum(notice)}
    return packages


def python_notices():
    packages = []
    for dist in metadata.distributions():
        name = dist.metadata.get('Name')
        if not name:
            continue
        files = {}
        for member in dist.files or ():
            target = Path(dist.locate_file(member))
            if not target.is_file():
                continue
            if '.dist-info/licenses/' in str(member).lower() or member.name.lower() in {'license', 'license.txt', 'copying', 'notice'}:
                files[str(member)] = checksum(target)
        declared = dist.metadata.get('License-Expression')
        if not declared and (license_field := dist.metadata.get('License')) and len(license_field) < 300 and '\n' not in license_field:
            declared = license_field
        packages.append({'name': name, 'version': dist.version, 'declared': declared, 'notice_files': files})
    return sorted(packages, key=lambda item: (item['name'].lower(), item['version']))


def vendor_notices():
    roots = [str(p) for p in (Path('/usr/lib'), Path('/usr/local/lib'), Path('/opt')) if p.is_dir()]
    listing = subprocess.check_output(
        ['find', *roots, '-type', 'f', '(', '-path', '*/pip/_vendor/vendor.txt',
         '-o', '-path', '*/ensurepip/_bundled/pip-*.whl', ')'], text=True
    ).splitlines()
    result = []
    for file in sorted(map(Path, listing)):
        if file.suffix == '.whl':
            with ZipFile(file) as archive:
                prefix = 'pip/_vendor/'
                run = vendor_records(archive.read(prefix + 'vendor.txt'), (
                    (n[len(prefix):], archive.read(n)) for n in archive.namelist()
                    if n.startswith(prefix) and is_notice(Path(n).name)
                ))
        else:
            directory = file.parent
            run = vendor_records(file.read_bytes(), (
                (str(p.relative_to(directory)), p.read_bytes()) for p in directory.rglob('*')
                if p.is_file() and is_notice(p.name)
            ))
        result.append({'source': str(file), 'source_sha256': checksum(file), 'packages': run})
    return result


def is_notice(name):
    return name.lower().startswith(('license', 'licence', 'copying', 'notice', 'copyright'))


def vendor_records(manifest, files):
    notices = {}
    for name, value in files:
        notices.setdefault(name.split('/')[0], {})[name] = hashlib.sha256(value).hexdigest()
    packages = []
    for line in manifest.decode().splitlines():
        if '==' not in line or line.lstrip().startswith('#'):
            continue
        package, version = line.strip().split('==', 1)
        directory = 'pkg_resources' if package.lower() == 'setuptools' else package.lower().replace('-', '_')
        packages.append({'name': package, 'version': version, 'directory': directory,
                         'notice_files': notices.get(directory, {})})
    return packages


if __name__ == '__main__':
    print(json.dumps({'debian': debian_notices(), 'python': python_notices(),
                      'pip_vendors': vendor_notices()}, sort_keys=True))
