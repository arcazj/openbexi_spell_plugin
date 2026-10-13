"""Run original native DATA/FILES oracles and independently observe real prompts."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from installed_provenance import capture_client, input_paths

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import qualify_host_adapter as host

ACTION_NAMES = dict(A='ABORT', R='REPEAT', S='RESEND', C='RECHECK', K='SKIP',
                    N='NOACTION', Q='CANCEL', H='HANDLE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=('files', 'data'))
    parser.add_argument('--image', default='openbexi-spell-host:v05-data-files')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT/('.qualification/v0.5/'+args.package)).resolve()/uuid.uuid4().hex
    project = output/'project'
    project.mkdir(parents=True)
    module = args.package + '_contracts'
    names = [f'conformance/{module}.py', 'conformance/run_data_files.py',
        'conformance/data_files_build.py', 'conformance/data_files.Dockerfile',
        'source_port/data_files_patches.py', 'scripts/qualify_host_adapter.py',
        'source_port/data_files_native_patches.py', 'conformance/data_files_native_build.py',
        'conformance/data_files_native.Dockerfile', 'conformance/inventory.json',
        'docs/reference/SPELL2.6.10-src.zip', 'docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    names = list(dict.fromkeys(names + input_paths(ROOT)))
    inputs = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    shutil.copyfile(ROOT/'conformance/installed_provenance.py',project/'installed_provenance.py')
    shutil.copyfile(ROOT/f'conformance/{module}.py', project/f'{module}.py')
    (project/'main.py').write_text(f'import {module}\n', encoding='utf-8')
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'], text=True).strip()
    host.IMAGE, host.EVIDENCE = image, output
    client = host.Client(project)
    observed = defaultdict(list)
    try:
        client.launch('main.py')
        integrated = capture_client(client, inputs)
        client.request('configurationDone')
        deadline = time.monotonic()+300
        while time.monotonic() < deadline:
            message = client.events.popleft() if client.events else client.next(deadline-time.monotonic())
            event, body = message.get('event'), message.get('body', {})
            if event == 'exited':
                if body['exitCode'] != 0:
                    for relative in ('data-files-active.json','data-files-results.json'):
                        try:
                            (output/relative).write_text(client.read_file(relative),encoding='utf-8')
                        except subprocess.CalledProcessError:
                            pass
                    subprocess.run(['docker','cp',client.name+':/tmp',str(output/'native-tmp')],capture_output=True,timeout=20)
                assert body['exitCode'] == 0, 'Native harness failed: inspect retained transcript'
                break
            if event != 'openbexi/inputRequest':
                continue
            active = json.loads(client.read_file('data-files-active.json'))
            key = active['check']
            expected = active['prompts'][len(observed[key])]
            choices = [ACTION_NAMES.get(value,value) for value in body['choices'].split('\x04')]
            observed[key].append(dict(choices=choices, text=body['text']))
            if expected.get('repair'):
                relative = expected['repair']
                assert relative.startswith('files-owned-') and '..' not in Path(relative).parts
                subprocess.run(['docker','exec',client.name,'python','-c',
                    'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("controller repaired\\n")',
                    '/workspace/'+relative], capture_output=True, check=True, timeout=10)
            answer = expected['answer']
            if expected.get('raw'):
                client.request('openbexi/input', text=answer)
            else:
                assert answer in choices, (answer, choices)
                client.request('openbexi/input', text=str(choices.index(answer)))
        else:
            raise TimeoutError('Native oracles did not exit')
        report = json.loads(client.read_file('data-files-results.json'))
        for key, row in report['checks'].items():
            expected = row.pop('expected_prompts')
            actual = observed.get(key, [])
            row['controller_prompts'] = actual
            if len(actual) != len(expected) or any(
                    want.get('choices') is not None and got['choices'] != want['choices']
                    for got,want in zip(actual,expected)):
                row['passed'] = False
                row['controller_error'] = {'expected':expected,'actual':actual}
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest for name,digest in inputs.items()), 'Inputs changed during execution'
        report.update(runtime_image=image, inputs=inputs)
        report['runtime_sources'] = {'integrated':integrated}
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        failures = {key: row.get('error',row.get('controller_error')) for key,row in report['checks'].items() if not row['passed']}
        print(json.dumps(dict(evidence=str(output),checks=len(report['checks']),
            contracts=len({item for row in report['checks'].values() for item in row['contracts']}),failures=failures),indent=2))
        return bool(failures)
    finally:
        client.close(args.package+'-contracts')


if __name__ == '__main__':
    raise SystemExit(main())
