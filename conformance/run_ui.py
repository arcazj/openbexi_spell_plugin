"""Qualify procedure text, item notifications and typed prompts on original IPC."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='openbexi-spell-host:v05-common')
    args = parser.parse_args()
    output = ROOT/'.qualification/v0.5/ui'/uuid.uuid4().hex
    output.mkdir(parents=True)
    names = ('conformance/ui_controller.py', 'conformance/ui_contracts.py', 'conformance/run_ui.py',
        'conformance/ui_edge_controller.py', 'conformance/ui_edges.py',
        'conformance/build_common_patch.py', 'conformance/common.Dockerfile', 'source_port/patches.py',
        'conformance/ui_native_build.py', 'conformance/ui_native.Dockerfile',
        'source_port/ui_native_patches.py', 'distribution/incremental_native.py',
        'conformance/combined_native_build.py', 'conformance/combined_native.Dockerfile',
        'source_port/flow_patches.py', 'source_port/flow_analyze.py',
        'conformance/dta_native_build.py', 'conformance/dta_native.Dockerfile',
        'source_port/dta_native_patches.py', 'source_port/dta_time_patches.py',
        'source_port/data_files_native_patches.py',
        'source_port/dta_ipc_patches.py', 'conformance/dta_ipc_build.py',
        'conformance/dta_ipc.Dockerfile', 'conformance/dta_ipc.Dockerfile.dockerignore',
        'docs/reference/SPELL2.6.10-src.zip', 'docs/reference/SPELL - Language Reference - 2.4.4.pdf')
    inputs = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    normalized = {name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                  for name in names if name.endswith('.py')}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name = 'openbexi-ui-conformance-' + uuid.uuid4().hex
    def read(relative):
        raw = subprocess.check_output(['docker','cp',name+':/workspace/'+relative,'-'],timeout=15)
        with tarfile.open(fileobj=io.BytesIO(raw)) as bundle:
            return bundle.extractfile(bundle.getmembers()[0]).read()
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-I','/workspace/controller.py'],check=True,capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            for target, content in (('controller.py',(ROOT/'conformance/ui_controller.py').read_bytes()),
                ('ui_contracts.py',(ROOT/'conformance/ui_contracts.py').read_bytes()),
                ('ui_edge_controller.py',(ROOT/'conformance/ui_edge_controller.py').read_bytes()),
                ('edges.py',(ROOT/'conformance/ui_edges.py').read_bytes()),
                ('main.py',b'import ui_contracts\n')):
                item = tarfile.TarInfo(target)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                bundle.addfile(item,io.BytesIO(content))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        run = subprocess.run(['docker','start','-a',name],capture_output=True,timeout=750)
        (output/'controller.log').write_bytes(run.stdout + run.stderr)
        for relative in ('ui-wire.json','ui-answers.json','ui-results.json','ui-complete.json','ui-runtime.json',
                         'ui-edge-wire.json','ui-edge-observations.json','ui-edge-results.json'):
            try:
                (output/relative).write_bytes(read(relative))
            except subprocess.CalledProcessError:
                if run.returncode == 0:
                    raise
        assert run.returncode == 0, str(output/'controller.log')
        wire = json.loads((output/'ui-wire.json').read_bytes())
        answers = json.loads((output/'ui-answers.json').read_bytes())
        report = json.loads((output/'ui-results.json').read_bytes())
        runtime = json.loads((output/'ui-runtime.json').read_bytes())
        if 'ui_manifest' in runtime:
            for recipe, digest in runtime['ui_manifest']['recipes'].items():
                source = next(name for name in names if name.endswith('/' + recipe))
                assert digest in (inputs[source], normalized.get(source)), 'Installed patch recipe is stale: ' + recipe
        messages = [event.get('message',{}) for event in wire]
        writes = [row['fields'] for row in messages if row.get('id') == 'MSG_WRITE' and row.get('fields',{}).get('Scope') == '1']
        items = [row['fields'] for row in messages if row.get('id') == 'MSG_NOTIFICATION' and row.get('fields',{}).get('DataType') == 'ITEM']
        for identifier, row in report['checks'].items():
            expected = row.pop('expected')
            observed_answers = [entry for entry in answers if entry['check'] == identifier]
            row['controller_answers'] = observed_answers
            observed_writes = [entry for entry in writes if entry.get('Text','').startswith('UI:' + identifier)]
            observed_items = [entry for entry in items if entry.get('ItemName','').startswith('UI:' + identifier)]
            row['writes'], row['items'] = observed_writes, observed_items
            try:
                assert len(observed_answers) == len(expected['prompts']), 'Prompt count mismatch'
                if identifier.startswith(('display:', 'notify:')):
                    assert len(observed_writes) == len(expected['writes']), ('Write count mismatch', observed_writes, expected['writes'])
                    assert len(observed_items) == len(expected['items']), ('Item count mismatch', observed_items, expected['items'])
                # Native INFO buffering and immediate warning/error delivery may
                # reorder writes. Match complete values without imposing order.
                for wanted in expected['writes']:
                    assert sum(all(actual.get(key) == value for key,value in wanted.items())
                               for actual in observed_writes) == 1, (wanted, observed_writes)
                for wanted in expected['items']:
                    assert sum(all(actual.get(key) == value for key,value in wanted.items())
                               for actual in observed_items) == 1, (wanted, observed_items)
            except AssertionError as error:
                row.update(passed=False, controller_error=str(error))
        report['checks'].update(json.loads((output/'ui-edge-results.json').read_bytes())['checks'])
        assert all(hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest for source,digest in inputs.items())
        report.update(inputs=inputs,lf_normalized_inputs=normalized,runtime_image=image,runtime_sources=runtime)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        failures = {key:row.get('error',row.get('controller_error')) for key,row in report['checks'].items() if not row['passed']}
        print(json.dumps(dict(evidence=str(output), checks=len(report['checks']), failures=failures),indent=2))
        return bool(failures)
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__ == '__main__':
    raise SystemExit(main())
