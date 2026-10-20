"""Build and inspect two reproducible, offline shared-provider wheels."""
import argparse
import base64
import configparser
import csv
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import uuid
from importlib.metadata import version
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATE_EPOCH = '1767225600'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_wheel(path, project):
    """Check declared requirements, entry points, and every RECORD payload."""
    with ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate wheel members'
        metadata_name, = (name for name in names if name.endswith('.dist-info/METADATA'))
        prefix = metadata_name.rsplit('/', 1)[0]
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        assert metadata['Name'] == project['name'], 'Unexpected distribution name'
        assert metadata['Version'] == project['version'], 'Unexpected package version'
        python_specifiers = lambda value: {item.strip() for item in value.split(',')}
        assert python_specifiers(metadata['Requires-Python']) == python_specifiers(project['requires-python']), 'Unexpected Python requirement'
        requirements = metadata.get_all('Requires-Dist', [])
        expected = list(project.get('dependencies', []))
        for extra, dependencies in project.get('optional-dependencies', {}).items():
            for dependency in dependencies:
                assert ';' not in dependency, 'Add explicit marker handling for marked optional requirements'
                expected.append(f'{dependency}; extra == "{extra}"')
        normalize = lambda value: re.sub(r'\s+', '', value).replace("'", '"')
        assert sorted(map(normalize, requirements)) == sorted(map(normalize, expected)), 'Dependency metadata differs from source'
        assert sorted(metadata.get_all('Provides-Extra', [])) == sorted(project.get('optional-dependencies', {}))
        entry_points = configparser.ConfigParser()
        entry_points.optionxform = str
        entry_points.read_string(archive.read(prefix + '/entry_points.txt').decode())
        entries = {group: dict(entry_points[group]) for group in entry_points.sections()}
        assert entries == project.get('entry-points', {}), 'Entry points differ from source'
        record_name = prefix + '/RECORD'
        records = list(csv.reader(io.StringIO(archive.read(record_name).decode('utf-8'))))
        assert len(records) == len(names), 'RECORD does not cover the complete wheel'
        assert len({row[0] for row in records}) == len(records), 'Duplicate RECORD entries'
        assert {row[0] for row in records} == set(names), 'RECORD membership differs from wheel'
        payloads = {}
        for name, digest, size in records:
            if name == record_name:
                assert not digest and not size, 'RECORD must not hash itself'
                continue
            data = archive.read(name)
            actual = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            assert digest == 'sha256=' + actual, f'Invalid RECORD digest for {name}'
            assert int(size) == len(data), f'Invalid RECORD size for {name}'
            payloads[name] = hashlib.sha256(data).hexdigest()
        return {'name': metadata['Name'], 'version': metadata['Version'],
                'requires_python': metadata['Requires-Python'], 'requires_dist': requirements,
                'entry_points': entries, 'record_verified': True,
                'record_entries': len(records), 'payload_sha256': payloads}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v06/shared-pair',
                        help='Parent directory for a unique evidence directory')
    args = parser.parse_args(argv)
    output = args.output.resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    report = {'passed': False, 'builds': [], 'builder_sha256': sha(Path(__file__)),
              'python': sys.version, 'setuptools': version('setuptools'),
              'source_date_epoch': SOURCE_DATE_EPOCH,
              'scope': 'Shared wheel reproducibility and metadata/RECORD checks; installation, upgrade, and release acceptance are separate'}
    try:
        assert report['setuptools'] == '80.9.0', 'Use the pinned setuptools 80.9.0 backend'
        report['source_base_commit'] = subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        names = subprocess.check_output(
            ['git', '-C', str(ROOT), 'ls-files', '-z', '--', 'shared_plugin']).decode().split('\0')
        files = [ROOT / name for name in names if name]
        assert files, 'No tracked shared-provider sources'
        inputs = {path.relative_to(ROOT).as_posix(): sha(path) for path in files}
        report['inputs'] = inputs
        configuration = tomllib.loads((ROOT / 'shared_plugin/pyproject.toml').read_text(encoding='utf-8'))
        assert configuration['build-system']['requires'] == ['setuptools==80.9.0']
        project = configuration['project']
        report['version'] = project['version']
        for name in ('a', 'b'):
            build = output / name
            source = build / 'source'
            for path in files:
                data = path.read_bytes()
                assert hashlib.sha256(data).hexdigest() == inputs[path.relative_to(ROOT).as_posix()], 'Source changed during capture'
                target = source / path.relative_to(ROOT / 'shared_plugin')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            command = [sys.executable, '-I', '-m', 'pip', '--disable-pip-version-check',
                       'wheel', '--no-cache-dir', '--no-index', '--no-deps',
                       '--no-build-isolation', '--wheel-dir', str(build / 'wheels'), str(source)]
            result = subprocess.run(command, capture_output=True, timeout=120,
                                    env=dict(os.environ, SOURCE_DATE_EPOCH=SOURCE_DATE_EPOCH))
            (build / 'build.log').write_bytes(result.stdout + result.stderr)
            result.check_returncode()
            wheel, = (build / 'wheels').glob('*.whl')
            report['builds'].append({'wheel': str(wheel), 'sha256': sha(wheel),
                                     'source': str(source), 'command': command,
                                     'inspection': inspect_wheel(wheel, project)})
        assert report['builds'][0]['sha256'] == report['builds'][1]['sha256'], 'Independent wheels differ'
        assert all(sha(ROOT / name) == digest for name, digest in inputs.items()), 'Source changed during builds'
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'output': str(output), 'passed': report['passed'],
                          'builds': [{'wheel': item['wheel'], 'sha256': item['sha256']} for item in report['builds']],
                          'error': report.get('error')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
