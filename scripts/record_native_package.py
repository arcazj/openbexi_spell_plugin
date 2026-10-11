"""Verify the isolated native package milestone before recording acceptance.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--accept-v02', action='store_true', help='Record reviewed v0.2 native-foundation acceptance, retaining later conformance/distribution gates')
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    root = Path(__file__).resolve().parent.parent
    results = [json.loads((evidence / 'distribution' / ('package-' + name + '.json')).read_text()) for name in ('a', 'b')]
    if results[0] != results[1]:
        raise ValueError('The two package builds have different identities')
    result = results[0]
    for name in ('a', 'b'):
        wheel = evidence / 'distribution' / name / result['wheel']
        if sha(wheel.read_bytes()) != result['sha256']:
            raise ValueError('Wheel bytes differ from build manifest: ' + name)
    manifest = result['manifest']
    inputs = manifest['inputs']
    actual = {p.relative_to(root / 'source_port').as_posix(): sha(p.read_bytes())
              for p in (root / 'source_port').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    if inputs != actual:
        raise ValueError('Package recipe/source snapshot differs from the working tree: ' +
                         str(sorted(name for name in inputs.keys() | actual.keys() if inputs.get(name) != actual.get(name))))
    installed = json.loads((evidence / 'installed/installed-runtime.json').read_text())
    if installed['tests'] != 7 or any(installed[key] for key in ('failures', 'errors', 'skips')):
        raise ValueError('Fresh-image installed behavior did not pass')
    if installed.get('installed_peer_sha256')!=sha((evidence/'native/installed_peer').read_bytes()):
        raise ValueError('Installed IPC peer differs from its build artifact')
    if 'INSTALLED_LISTENER_CONTEXT_EXECUTOR_CLOSED' not in (evidence/'installed/installed-peer.log').read_text():
        raise ValueError('Installed listener/context/executor workflow did not complete')
    if (evidence/'installed/installed-context-result.txt').read_text()!='42':
        raise ValueError('Installed context procedure did not produce its result')
    links=installed.get('installed_example_links',{})
    target='/opt/spell-test-env/lib/python3.13/site-packages/spell_native/bin/SPELL-Executor_v3'
    if links!={'SPELL-Executor':target,'SPELL-Executor_v3':target}:
        raise ValueError('Installed example executor aliases differ')
    if not installed.get('no_build_tree') or not installed.get('uninstall_preserves_plain_python'):
        raise ValueError('Installation isolation or removal was not established')
    if (installed['wheel'], installed['wheel_sha256']) != (result['wheel'], result['sha256']):
        raise ValueError('Fresh environment tested a different artifact')
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None:
            raise ValueError('Corrupt wheel')
        for name, digest in manifest['native_artifacts'].items():
            if sha(archive.read('spell_native/bin/' + name)) != digest:
                raise ValueError('Native wheel payload differs: ' + name)
        for name, digest in manifest['python_sources'].items():
            if sha(archive.read(name)) != digest:
                raise ValueError('Python wheel payload differs: ' + name)
        native_bytes = archive.read('spell_native/provenance/NATIVE_SERVICE_RECOVERY_POLICY_QUALIFICATION.json')
        if sha(native_bytes) != manifest['qualification_sha256']:
            raise ValueError('Native qualification identity differs')
        native = json.loads(native_bytes)
        authority = archive.read('spell_native/provenance/SPELL2.6.10-src.zip')
        if sha(authority) != manifest['archive_sha256']:
            raise ValueError('Corresponding source archive differs')
        for name, digest in inputs.items():
            if sha(archive.read('spell_native/provenance/source_port/' + name)) != digest:
                raise ValueError('Corresponding recipe differs: ' + name)
    # Bind the native binary payload to the independent gate carried in the wheel.
    for name, digest in manifest['native_artifacts'].items():
        if native['artifacts'][name]['sha256'] != digest:
            raise ValueError('Packaged binary was not the qualified binary: ' + name)
    if args.accept_v02:
        if manifest['version']!='0.2.0':
            raise ValueError('v0.2 acceptance requires the final 0.2.0 artifact')
        policy=native.get('service_recovery_policy',{})
        if (policy.get('native_api_rejections_before_python')!=2 or
                policy.get('command_rejections_before_body')!=2 or
                policy.get('live_reconnect_repetitions_per_kind')!=3):
            raise ValueError('Native lifecycle and recovery policy acceptance incomplete')
    report = {'milestone': 'Installed original-source native diagnostic package',
              'release': 'v0.2 native foundation qualified' if args.accept_v02 else 'v0.2 native foundation candidate; acceptance recorded separately',
              'version': result['manifest']['version'],'v02_foundation_qualified':args.accept_v02,
              'scope': 'Two identical packages from one qualified native build; fresh Debian image install/run/import/removal',
              'full_release_qualified': False, 'full_native_rebuild_reproducibility': False,
              'package': result, 'installed_runtime': installed, 'native': native,
              'recorder_sha256': sha(Path(__file__).read_bytes()),
              'remaining': ([] if args.accept_v02 else ['Final native foundation acceptance review']) +
                           ['Production platform/toolchain locks and independent native rebuild reproducibility',
                            'IDE host plugins, original DSS drivers, full conformance and v0.6 distribution']}
    path = root / 'docs/NATIVE_PACKAGE_QUALIFICATION.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'wheel': result['wheel'], 'sha256': result['sha256'],
                      'installed_tests': installed['tests'], 'report': str(path)}))


if __name__ == '__main__':
    main()
