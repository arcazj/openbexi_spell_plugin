"""Compare declared license bytes in staged wheel/source pairs and collect their hashes."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_pair(directory, wheel_name, manifest):
    wheel = directory / wheel_name
    stem = '-'.join(wheel.name.split('-')[:2])
    source = directory / (stem + '.tar.gz')
    for item in (wheel, source):
        if digest(item.read_bytes()) != manifest['files'][item.name]:
            raise ValueError('Archive differs from its build receipt: ' + item.name)
    with zipfile.ZipFile(wheel) as distribution, tarfile.open(source) as sdist:
        metadata_name, = [n for n in distribution.namelist() if n.endswith('.dist-info/METADATA')]
        info = BytesParser().parsebytes(distribution.read(metadata_name))
        prefix = metadata_name.rsplit('/', 1)[0] + '/licenses/'
        source_info = BytesParser().parsebytes(sdist.extractfile(stem + '/PKG-INFO').read())
        for key in ('Name', 'Version', 'License-Expression', 'License-File'):
            if not info.get_all(key) or info.get_all(key) != source_info.get_all(key):
                raise ValueError('Metadata differs: ' + key + ' in ' + wheel.name)
        licenses = {}
        for name in info.get_all('License-File'):
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Invalid license path')
            contents = distribution.read(prefix + name)
            if not contents.strip() or contents != sdist.extractfile(stem + '/' + name).read():
                raise ValueError('License bytes differ: ' + name)
            licenses[name] = digest(contents)
        bundled = {name: digest(distribution.read(name)) for name in distribution.namelist()
                   if '/licenses/' in name.lower() and not name.startswith(prefix) and not name.endswith('/')}
        return dict(name=info['Name'], version=info['Version'], expression=info['License-Expression'],
                    commit=manifest['commit'], wheel=wheel.name, wheel_sha256=manifest['files'][wheel.name],
                    sdist=source.name, sdist_sha256=manifest['files'][source.name],
                    declared_license_files=licenses, additional_bundled_license_files=bundled)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    items = []
    for directory in args.directories:
        manifest = json.loads((directory / 'packages.json').read_bytes())
        items.extend(inspect_pair(directory, name, manifest) for name in sorted(manifest['files']) if name.endswith('.whl'))
    if len({row['name'] for row in items}) != 6:
        raise ValueError('Expected six distinct release packages')
    result = dict(status='PASS', scope='Declared wheel and sdist license texts and package checksums', packages=items)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
