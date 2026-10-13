"""Build two offline host wheels from independent, hash-bound source copies."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import uuid
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert version('setuptools') == '80.9.0', 'Use the pinned host build backend'
    output = ROOT / '.qualification/v0.6/host-candidates' / uuid.uuid4().hex
    output.mkdir(parents=True)
    names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z', '--', 'host_plugin']).decode().split('\0')
    files = [ROOT / name for name in names if name]
    inputs = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    package_version = tomllib.loads((ROOT / 'host_plugin/pyproject.toml').read_text())['project']['version']
    report = {'passed': False, 'version': package_version, 'inputs': inputs,
              'builder_sha256': sha(Path(__file__)),
              'source_base_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],text=True).strip(),
              'setuptools': version('setuptools'), 'python': sys.version,
              'source_date_epoch': '1767225600', 'builds': [],
              'scope': 'Host wheel reproducibility only; no native or release acceptance'}
    try:
        for name in ('a', 'b'):
            build = output / name
            source = build / 'source'
            for path in files:
                target = source / path.relative_to(ROOT / 'host_plugin')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            command = [sys.executable, '-m', 'pip', 'wheel', '--no-cache-dir', '--no-index',
                       '--no-deps', '--no-build-isolation', '--wheel-dir', str(build / 'wheels'), str(source)]
            result = subprocess.run(command, capture_output=True, timeout=120,
                                    env=dict(os.environ, SOURCE_DATE_EPOCH=report['source_date_epoch']))
            (build / 'build.log').write_bytes(result.stdout + result.stderr)
            result.check_returncode()
            wheel, = (build / 'wheels').glob('*.whl')
            report['builds'].append({'wheel': str(wheel), 'sha256': sha(wheel)})
        assert report['builds'][0]['sha256'] == report['builds'][1]['sha256']
        assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'output': str(output), 'passed': report['passed'], 'builds': report['builds']}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
