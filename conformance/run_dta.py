"""Run DTA oracles in the original native executor, retaining raw IPC and hashes."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid
import datetime
import re
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def digest(content):
    return hashlib.sha256(content).hexdigest()


def item_matches(actual, wanted):
    for key, value in wanted.items():
        if key != 'time':
            if actual.get(key) != value:
                return False
        elif value['kind'] == 'absolute':
            try:
                if datetime.datetime.fromisoformat(actual['ItemValue']) != datetime.datetime.fromisoformat(value['value']):
                    return False
            except (KeyError, ValueError):
                return False
        else:
            match = re.fullmatch(r'([+-])(?:(\d+) )?(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?', actual.get('ItemValue', ''))
            if not match:
                return False
            sign, days, hours, minutes, seconds, fraction = match.groups()
            micros = ((int(days or 0)*24+int(hours))*3600+int(minutes)*60+int(seconds))*1000000+int((fraction or '').ljust(6, '0'))
            if (-micros if sign == '-' else micros) != value['microseconds']:
                return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-host:v05-ui-flow-data-final')
    parser.add_argument('--groups', default='', help='Comma-separated groups for retained diagnostic runs')
    args = parser.parse_args()
    output = ROOT / '.qualification/v0.5/dta' / uuid.uuid4().hex
    output.mkdir(parents=True)
    sources = ['conformance/dta_controller.py', 'conformance/dta_contracts.py', 'conformance/run_dta.py',
               'conformance/dta_native_build.py', 'conformance/dta_native.Dockerfile', 'distribution/incremental_native.py',
               'source_port/flow_analyze.py',
               'docs/reference/SPELL2.6.10-src.zip', 'docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    sources += ['source_port/' + name for name in (
        'patches.py', 'native_patches.py', 'dta_native_patches.py', 'dta_time_patches.py',
        'data_files_patches.py', 'data_files_native_patches.py', 'ui_native_patches.py', 'flow_patches.py')]
    sources += ['source_port/dta_ipc_patches.py', 'conformance/dta_ipc_build.py',
                'conformance/dta_ipc.Dockerfile', 'conformance/dta_ipc.Dockerfile.dockerignore']
    sources = list(dict.fromkeys(sources + input_paths(ROOT)))
    inputs = {name: digest((ROOT/name).read_bytes()) for name in sources}
    normalized = {name: digest((ROOT/name).read_bytes().replace(b'\r\n', b'\n'))
                  for name in sources if name.endswith('.py')}
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    name = 'openbexi-dta-conformance-' + uuid.uuid4().hex
    def read(relative):
        content = subprocess.check_output(['docker', 'cp', name + ':/workspace/' + relative, '-'], timeout=20)
        with tarfile.open(fileobj=io.BytesIO(content)) as bundle:
            return bundle.extractfile(bundle.getmembers()[0]).read()
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none', '--cap-drop', 'ALL',
                        '--security-opt', 'no-new-privileges', '--pids-limit', '256', '--entrypoint', 'python',
                        image, '-I', '/workspace/controller.py'], check=True, capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as bundle:
            entry = ('import os\nos.environ["DTA_GROUPS"] = ' + repr(args.groups) + '\nimport dta_contracts\n').encode()
            for target, content in [('main.py', entry),
                                    ('installed_provenance.py', (ROOT/'conformance/installed_provenance.py').read_bytes()),
                                    ('dta_contracts.py', (ROOT/'conformance/dta_contracts.py').read_bytes()),
                                    ('controller.py', (ROOT/'conformance/dta_controller.py').read_bytes())]:
                (output/target).write_bytes(content)
                item = tarfile.TarInfo(target)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                bundle.addfile(item, io.BytesIO(content))
        subprocess.run(['docker', 'cp', '-a', '-', name + ':/workspace'], input=archive.getvalue(), check=True, capture_output=True)
        run = subprocess.run(['docker', 'start', '-a', name], capture_output=True, timeout=300)
        (output/'controller.log').write_bytes(run.stdout + run.stderr)
        for relative in ('dta-active.json', 'dta-results.json', 'dta-wire.json', 'dta-answers.json', 'dta-complete.json', 'dta-runtime.json'):
            try:
                (output/relative).write_bytes(read(relative))
            except subprocess.CalledProcessError:
                pass
        subprocess.run(['docker', 'cp', name + ':/tmp', str(output/'native-tmp')], capture_output=True, timeout=30)
        metadata = dict(runtime_image=image, inputs=inputs, lf_normalized_inputs=normalized, controller_exit=run.returncode)
        (output/'execution.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8', newline='\n')
        assert run.returncode == 0, str(output/'controller.log')
        report = json.loads((output/'dta-results.json').read_bytes())
        runtime = json.loads((output/'dta-runtime.json').read_bytes())
        verify_capture(runtime.get('integrated'), inputs, normalized)
        if 'manifest' in runtime:
            for recipe, expected in runtime['manifest']['recipes'].items():
                source = next(source for source in sources if source.endswith('/' + recipe))
                assert expected in (inputs[source], normalized.get(source)), 'Installed patch is stale: ' + source
        report['runtime_sources'] = runtime
        wire = json.loads((output/'dta-wire.json').read_bytes())
        observed = json.loads((output/'dta-answers.json').read_bytes())
        messages = [row.get('message', {}) for row in wire]
        items = [row['fields'] for row in messages if row.get('id') == 'MSG_NOTIFICATION'
                 and row.get('fields', {}).get('DataType') == 'ITEM']
        for identifier, row in report['checks'].items():
            expected = row.pop('expected')
            answers = [value for value in observed if value['check'] == identifier]
            selected = [value for value in items if value.get('ItemName', '').startswith('DTA:' + identifier + ':')]
            row.update(controller_answers=answers, items=selected, rejections=expected['rejections'])
            try:
                assert len(answers) == len(expected['prompts']), ('Prompt count', len(answers), expected['prompts'])
                for wanted in expected['items']:
                    assert any(item_matches(actual, wanted) for actual in selected), ('Missing ITEM', wanted)
                for variable, sequence in expected['sequences'].items():
                    actual = [[value.get('ItemStatus'), value.get('ItemValue')] for value in selected if value.get('ItemName') == variable]
                    assert actual == sequence, ('ITEM sequence', variable, sequence, actual)
            except AssertionError as error:
                row.update(passed=False, controller_error=str(error))
        assert all(digest((ROOT/name).read_bytes()) == value for name, value in inputs.items()), 'Inputs changed'
        report.update(metadata)
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
        failures = {key: row.get('error', row.get('controller_error')) for key, row in report['checks'].items() if not row['passed']}
        print(json.dumps(dict(evidence=str(output), checks=len(report['checks']), failures=failures), indent=2))
        return bool(failures)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
