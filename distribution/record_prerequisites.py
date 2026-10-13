"""Bind current distribution prerequisite evidence without accepting a release."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bound(path):
    return {'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def record(rebuild, hosts, openbexi, artifact_root):
    result_path = rebuild / 'result.json'
    result = json.loads(result_path.read_text())
    assert result['passed'] and all(result['checks'].values())
    assert result['build_cache_enabled'] is False and result['same_build_repackaging'] is False
    assert sha(rebuild / 'inputs.json') == result['inputs_sha256']
    for name, expected in json.loads((rebuild / 'inputs.json').read_text()).items():
        source = (rebuild / 'source' / name).resolve()
        assert source.is_relative_to((rebuild / 'source').resolve()) and sha(source) == expected
    wheels = []
    for label, package in zip(('a', 'b'), result['packages']):
        wheel = rebuild / label / 'distribution/wheels' / package['wheel']
        assert sha(wheel) == package['sha256']
        with zipfile.ZipFile(wheel) as archive:
            for name, expected in package['native_artifacts'].items():
                assert hashlib.sha256(archive.read('spell_native/bin/' + name)).hexdigest() == expected
        wheels.append(bound(wheel))
    assert wheels[0]['sha256'] == wheels[1]['sha256']
    workflow = {}
    for kind, folder in {**hosts, 'openbexi': openbexi}.items():
        path = folder / 'result.json'
        data = json.loads(path.read_text())
        assert data['passed'] and data['v06_release_accepted'] is False
        row = dict(bound(path), runtime_image=data['image'])
        if kind == 'openbexi':
            child = folder / data['result']
            assert sha(child) == data['result_sha256']
            assert json.loads(child.read_text())['runtime_images'] == [data['image']]
        else:
            for phase in ('installed', 'removed'):
                child = folder / data[phase]['result']
                assert sha(child) == data[phase]['sha256']
                assert json.loads(child.read_text())['runtime_images'] == [data['image']]
            row['sdk'] = data['installed']['sdk']
        workflow[kind] = row
    artifacts = {}
    for name, pattern in (('jetbrains_zip', 'jetbrains-{}/openbexi-spell-0.3.0.zip'),
                          ('host_wheel', 'host-wheels-{}/openbexi_spell_host-0.3.0-py3-none-any.whl')):
        pair = [artifact_root / pattern.format(label) for label in ('a', 'b')]
        assert sha(pair[0]) == sha(pair[1])
        artifacts[name] = [bound(path) for path in pair]
    verdicts = {}
    for product in ('PY-261.24374.152', 'IU-262.10968.63'):
        path = artifact_root / 'verifier' / product / 'plugins/org.openbexi.spell/0.3.0/verification-verdict.txt'
        verdict = path.read_text().strip()
        assert verdict.startswith('Compatible.'), verdict
        verdicts[product] = dict(bound(path), verdict=verdict)
    export = rebuild / 'toolchain-export.json'
    toolchain = json.loads(export.read_text())
    assert toolchain['image'] == result['toolchain_image']
    assert sha(rebuild / toolchain['archive']) == toolchain['sha256']
    return {
        'prerequisites_passed': True, 'v05_accepted': False, 'v06_accepted': False,
        'scope': 'Independent COMMON-snapshot native rebuild and current installed host prerequisites',
        'native_rebuild': dict(bound(result_path), checks=result['checks'],
            source_snapshot_inputs=bound(rebuild / 'inputs.json'), wheels=wheels,
            native_artifacts=result['packages'][0]['native_artifacts']),
        'toolchain_export': dict(metadata=bound(export), **toolchain),
        'host_workflows': workflow, 'host_artifacts': artifacts, 'plugin_verifier': verdicts,
        'remaining': ['Full v0.5 acceptance', 'Final integrated DATA/FLOW/UI native rebuilds',
                      'Versioned upgrade paths', 'Final artifact host reruns',
                      'Final shipped DSS image/runtime qualification',
                      'Snapshot-locked apt toolchain reconstruction', 'Live noVNC closure/scroll verification'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild', type=Path, required=True)
    parser.add_argument('--pycharm', type=Path, required=True)
    parser.add_argument('--intellij', type=Path, required=True)
    parser.add_argument('--openbexi', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, default=ROOT / '.qualification/v0.6')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/V06_QUALIFICATION.json')
    args = parser.parse_args()
    result = record(args.rebuild.resolve(), {'pycharm': args.pycharm.resolve(),
                    'intellij': args.intellij.resolve()}, args.openbexi.resolve(), args.artifacts.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'prerequisites_passed': result['prerequisites_passed'],
                      'v06_accepted': result['v06_accepted'], 'output': str(args.output)}))
