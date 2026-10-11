"""Reject mixed candidates and record release-host evidence with exact identities."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True, help='JSON map of named evidence paths')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = {key: (ROOT / value).resolve(strict=True) for key, value in json.loads(args.evidence.read_text()).items()}
    reports = {}
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'openbexi-spell-host:0.3.0'], text=True))[0]
    for key in ['openbexi', 'lifecycle', 'pycharm', 'intellij', 'pycharm_removal', 'intellij_removal']:
        report = json.loads(paths[key].read_text())
        assert report['passed'] and report['checks'], (key, report)
        if 'image' in report:
            assert report['image'] == image['Id'], (key, 'wrong native image')
        if key.startswith(('pycharm', 'intellij')):
            assert report['plugin_sha256'] == digest(paths['jetbrains_zip']), key
            assert report['runtime_images'] == [image['Id']], (key, 'wrong runtime image')
            for name, expected in report['inputs'].items():
                assert digest(ROOT / 'jetbrains' / name) == expected, name
        reports[key] = report
    assert reports['openbexi']['wheel_sha256'] == digest(paths['host_wheel'])
    assert reports['lifecycle']['script_sha256'] == digest(ROOT / 'scripts/qualify_host_lifecycle.py')
    adapter = json.loads(paths['adapter'].read_text())
    assert adapter['tests'] == 10 and not adapter['failures'] and not adapter['errors']
    assert adapter['image'] == image['Id']
    for name, expected in adapter['inputs'].items():
        assert digest(ROOT / name) == expected, name
    reports['adapter'] = adapter
    build = json.loads(paths['jetbrains_build'].read_text())
    assert build['sha256'] == digest(paths['jetbrains_zip'])
    for name, expected in build['inputs'].items():
        assert digest(ROOT / 'jetbrains' / name) == expected, name
    reports['jetbrains_build'] = build
    for key in ['pycharm_verdict', 'intellij_verdict']:
        verdict = paths[key].read_text()
        assert verdict.startswith('Compatible.'), (key, verdict)
        reports[key] = verdict
    with zipfile.ZipFile(paths['host_wheel']) as wheel:
        for path in (ROOT / 'host_plugin/src/openbexi_spell_host').glob('*.py'):
            assert wheel.read('openbexi_spell_host/' + path.name) == path.read_bytes(), path.name
    reports['native_foundation_report_sha256'] = digest(ROOT / 'docs/NATIVE_HOST_FOUNDATION_QUALIFICATION.json')
    bridge = json.loads(subprocess.check_output(['docker', 'run', '--rm', '--network', 'none',
        '--entrypoint', 'cat', image['Id'], '/bridge/build.json'], text=True))
    assert bridge['native_version'] == '0.3.0'
    reports['native_bridge'] = bridge
    source_paths = []
    for directory in ['host_plugin', 'host_runtime', 'jetbrains']:
        source_paths += [p for p in (ROOT / directory).rglob('*') if p.is_file()
            and not any(part in {'build', 'dist', '__pycache__'} or part.endswith('.egg-info') for part in p.parts)]
    source_paths += list((ROOT / 'scripts').glob('qualify_*host*.py'))
    source_paths += [Path(__file__)]
    report = {'release': '0.3.0', 'passed': True, 'scope': 'Local Development host integration',
        'image': {'id': image['Id'], 'os': image['Os'], 'architecture': image['Architecture']},
        'artifacts': {key: {'name': paths[key].name, 'sha256': digest(paths[key])}
                      for key in ['host_wheel', 'jetbrains_zip']},
        'evidence': {key: {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)} for key, path in paths.items()},
        'sources': {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(source_paths))},
        'checks': reports,
        'remaining_releases': ['0.4 original DSS drivers and three operating modes',
            '0.5 complete inventory conformance', '0.6 distribution and compatibility']}
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'release': report['release'], 'passed': True, 'image': image['Id'], 'report': str(args.output)}))


if __name__ == '__main__':
    main()
