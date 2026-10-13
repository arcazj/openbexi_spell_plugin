"""Run real native Notify checks and retain exact source/IPC evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid
from installed_provenance import input_paths, verify_capture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--ui-regression', action='store_true')
    args = parser.parse_args()
    output = ROOT/'.qualification/v0.6/notification'/uuid.uuid4().hex
    output.mkdir(parents=True)
    files = list(sorted((ROOT/'conformance').glob('notification*')))
    files += [ROOT/name for name in input_paths(ROOT)]
    if args.ui_regression:
        files += [ROOT/'conformance'/name for name in ('ui_controller.py','ui_contracts.py','ui_edge_controller.py','ui_edges.py')]
    files += [ROOT/'docs/reference/SPELL2.6.10-src.zip', ROOT/'docs/reference/SPELL - Language Reference - 2.4.4.pdf']
    inputs = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    normalized = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                  for path in files if path.suffix == '.py'}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name = 'openbexi-notification-' + uuid.uuid4().hex

    def read(relative):
        raw = subprocess.check_output(['docker','cp',name+':/workspace/'+relative,'-'],timeout=15)
        with tarfile.open(fileobj=io.BytesIO(raw)) as bundle:
            return bundle.extractfile(bundle.getmembers()[0]).read()

    report = dict(inputs=inputs, lf_normalized_inputs=normalized, runtime_image=image, checks={})
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-I','/workspace/notification_controller.py',
            *(['--ui-regression'] if args.ui_regression else [])],check=True,capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            sources = [(path.name,path.read_bytes()) for path in files
                       if path.parent == ROOT/'conformance' and path.suffix == '.py']
            sources.append(('main.py',b'import notification_contracts\n'))
            for target, content in sources:
                item = tarfile.TarInfo(target)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                bundle.addfile(item,io.BytesIO(content))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        run = subprocess.run(['docker','start','-a',name],capture_output=True,timeout=1050 if args.ui_regression else 240)
        (output/'controller.log').write_bytes(run.stdout + run.stderr)
        for relative in ('notification-wire.json','notification-answers.json','notification-results.json',
                         'notification-runtime.json','notification-complete.json','notification-checkpoints.json',
                         *(['notification-ui-regression.json','ui-regression.log'] if args.ui_regression else [])):
            try:
                (output/relative).write_bytes(read(relative))
            except subprocess.CalledProcessError:
                if run.returncode == 0:
                    raise
        assert run.returncode == 0, str(output/'controller.log')
        wire = json.loads((output/'notification-wire.json').read_bytes())
        answers = json.loads((output/'notification-answers.json').read_bytes())
        report['checks'] = json.loads((output/'notification-results.json').read_bytes())['checks']
        runtime = json.loads((output/'notification-runtime.json').read_bytes())
        verify_capture(runtime['baseline'], inputs, normalized)
        overlay = runtime['overlay']
        if overlay:
            assert overlay['recipe_sha256'] in (inputs['source_port/notification_patches.py'], normalized['source_port/notification_patches.py'])
        messages = [event.get('message',{}) for event in wire]
        items = [row['fields'] for row in messages if row.get('id') == 'MSG_NOTIFICATION'
                 and row.get('fields',{}).get('DataType') == 'ITEM']
        for identifier, row in report['checks'].items():
            expected = row['expected']
            observed = [entry for entry in items if entry.get('ItemName','').startswith('NOTIFY:' + identifier)]
            row['native_items'] = observed
            row['controller_answers'] = [entry for entry in answers if entry['check'] == identifier]
            # Prompt answer notifications contain unique answer data. Match all
            # native notification types so a changed type cannot hide an effect.
            prompt_notifications = [message['fields'] for message in messages if message.get('id') == 'MSG_NOTIFICATION'
                and any(prompt['answer'] in str(message.get('fields',{})) for prompt in expected['prompts'])]
            row['prompt_notifications'] = prompt_notifications
            try:
                assert len(observed) == len(expected['items']), ('Item count mismatch', observed, expected['items'])
                for wanted in expected['items']:
                    assert sum(all(actual.get(key)==value for key,value in wanted.items()) for actual in observed)==1
                assert len(row['controller_answers']) == len(expected['prompts'])
                enabled = sum(prompt['enabled'] for prompt in expected['prompts'])
                assert len(prompt_notifications) == enabled, ('Modifier suppression mismatch', prompt_notifications, enabled)
            except AssertionError as error:
                row.update(passed=False, controller_error=str(error))
        report['runtime_sources'] = runtime
        report['checks'].update(json.loads((output/'notification-checkpoints.json').read_bytes())['checks'])
        if args.ui_regression:
            regression = json.loads((output/'notification-ui-regression.json').read_bytes())
            report['ui_regression'] = regression
            report['checks'].update({'ui-regression:'+key:row for key,row in regression['checks'].items()})
        report['wire'] = wire
        assert all(hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest for source,digest in inputs.items())
    except Exception as error:
        report['infrastructure_error'] = repr(error)
    finally:
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)
    failures = {key:row.get('error',row.get('controller_error')) for key,row in report['checks'].items() if not row['passed']}
    print(json.dumps(dict(evidence=str(output), checks=len(report['checks']), failures=failures,
        infrastructure_error=report.get('infrastructure_error')),indent=2))
    return bool(failures or report.get('infrastructure_error'))


if __name__ == '__main__':
    raise SystemExit(main())
