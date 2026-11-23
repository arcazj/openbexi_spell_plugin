"""Inventory license metadata and notice hashes in the current isolated Linux image."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import subprocess


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


if __name__ == '__main__':
    print(json.dumps({'debian': debian_notices(), 'python': python_notices()}, sort_keys=True))
