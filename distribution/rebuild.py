"""Run two independent, offline native rebuilds from one immutable snapshot.

This is prerequisite qualification, not v0.6 release promotion. Accepted images
and artifacts are never changed. Every invocation gets a new evidence directory.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = 'openbexi-execution-python:3.13.15'
BASE_ID = 'sha256:280f64d0d798d06691354131d292e4fddd7a227c5f03381b8d70cdae501322dd'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(arguments, log):
    print('Running ' + ' '.join(map(str, arguments)), flush=True)
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run(list(map(str, arguments)), stdout=output, stderr=subprocess.STDOUT,
                                text=True, cwd=ROOT)
    if result.returncode:
        print(log.read_text(encoding='utf-8', errors='replace')[-12000:], flush=True)
        raise RuntimeError(f'Command exited {result.returncode}; evidence: {log}')


def image_id(tag):
    return subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'],
                                   text=True).strip()


def compare(evidence):
    packages = [json.loads((evidence / label / 'distribution/package-result.json').read_text())
                for label in ('a', 'b')]
    installed = [json.loads((evidence / label / 'installed/installed-runtime.json').read_text())
                 for label in ('a', 'b')]
    names = set(packages[0]['native_artifacts']) | set(packages[1]['native_artifacts'])
    native = {name: packages[0]['native_artifacts'].get(name) ==
                    packages[1]['native_artifacts'].get(name) for name in sorted(names)}
    checks = {
        'independent_native_rebuilds': True,
        'native_artifacts_identical': bool(native) and all(native.values()),
        'python_sources_identical': packages[0]['python_sources'] == packages[1]['python_sources'],
        'composition_identical': bool(packages[0].get('composition')) and packages[0]['composition'] == packages[1].get('composition'),
        'wheel_bytes_identical': packages[0]['sha256'] == packages[1]['sha256'],
        'fresh_install_and_removal': all(r['tests'] == 8 and not any(r[k] for k in
            ('failures', 'errors', 'skips')) and r['uninstall_preserves_plain_python'] and
            r['no_build_tree'] for r in installed),
    }
    return {'checks': checks, 'native_artifacts': native, 'packages': packages,
            'installed': installed, 'passed': all(checks.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v0.6/rebuild')
    parser.add_argument('--toolchain-image', help='Use an existing frozen toolchain instead of apt reconstruction')
    parser.add_argument('--toolchain-id', help='Require this exact retained toolchain sha256 identity')
    parser.add_argument('--export-toolchain', action='store_true', help='Retain a hash-bound docker image save archive')
    args = parser.parse_args()
    run_id = uuid.uuid4().hex
    evidence = args.output.resolve() / run_id
    snapshot = evidence / 'source'
    snapshot.mkdir(parents=True)
    for name in ('source_port', 'distribution'):
        shutil.copytree(ROOT / name, snapshot / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    archive = Path('docs/reference/SPELL2.6.10-src.zip')
    (snapshot / archive).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / archive, snapshot / archive)
    inputs = {p.relative_to(snapshot).as_posix(): sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}
    (evidence / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    report = {'run_id': run_id, 'passed': False, 'full_v05_accepted': False,
              'v06_release_accepted': False, 'inputs_sha256': sha(evidence / 'inputs.json'),
              'source_snapshot': 'source', 'build_cache_enabled': False,
              'native_build_network': 'none', 'same_build_repackaging': False}
    try:
        if args.toolchain_image:
            toolchain_tag = args.toolchain_image
            report['toolchain_origin'] = 'Explicit existing frozen image'
        else:
            actual_base = image_id(BASE)
            if actual_base != BASE_ID:
                raise ValueError('Pinned offline CPython base identity changed')
            report['base_image'] = actual_base
            toolchain_tag = 'openbexi-spell-toolchain:v06-' + run_id[:12]
            invoke(['docker', 'build', '--progress=plain', '--build-arg', 'BASE_IMAGE=' + BASE,
                    '-f', snapshot / 'distribution/toolchain.Dockerfile', '-t', toolchain_tag, snapshot],
                   evidence / 'toolchain-build.log')
        report['toolchain_image'] = image_id(toolchain_tag)
        if args.toolchain_id and report['toolchain_image'] != args.toolchain_id:
            raise ValueError('Frozen toolchain differs from the requested identity')
        report['toolchain_tag'] = toolchain_tag
        if args.export_toolchain:
            archive = evidence / 'toolchain-image.tar'
            invoke(['docker', 'image', 'save', '--output', archive, toolchain_tag],
                   evidence / 'toolchain-export.log')
            report['toolchain_archive'] = {'name': archive.name, 'sha256': sha(archive),
                                           'bytes': archive.stat().st_size}
        for label in ('a', 'b'):
            if image_id(toolchain_tag) != report['toolchain_image']:
                raise ValueError('Frozen toolchain image changed during qualification')
            invoke(['docker', 'build', '--no-cache', '--network=none', '--progress=plain',
                    '--build-arg', 'TOOLCHAIN_IMAGE=' + toolchain_tag,
                    '-f', snapshot / 'distribution/native.Dockerfile',
                    '--output', 'type=local,dest=' + str(evidence / label), snapshot],
                   evidence / (label + '-build.log'))
        if inputs != {p.relative_to(snapshot).as_posix(): sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}:
            raise ValueError('Immutable source snapshot changed during build')
        report.update(compare(evidence))
    except Exception as error:
        report['error'] = str(error)
    (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'evidence': str(evidence),
                      'error': report.get('error')}, indent=2), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
