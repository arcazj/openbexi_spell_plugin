"""Capture and qualify silent execution using actual original native IPC."""
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
    output = ROOT/'.qualification/v0.5/common-silence'/uuid.uuid4().hex
    output.mkdir(parents=True)
    names = ('conformance/silence_controller.py', 'conformance/silence_procedure.py',
             'conformance/run_silence.py', 'conformance/build_common_patch.py',
             'conformance/common.Dockerfile', 'source_port/patches.py',
             'docs/reference/SPELL2.6.10-src.zip',
             'docs/reference/SPELL - Language Reference - 2.4.4.pdf')
    inputs = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name = 'openbexi-common-silence-' + uuid.uuid4().hex
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
            for source, target in (('silence_controller.py','controller.py'),('silence_procedure.py','main.py')):
                content = (ROOT/'conformance'/source).read_bytes()
                item = tarfile.TarInfo(target)
                item.size, item.mode, item.uid, item.gid = len(content), 0o644, 10003, 10003
                bundle.addfile(item,io.BytesIO(content))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),check=True,capture_output=True)
        run = subprocess.run(['docker','start','-a',name],capture_output=True,timeout=100)
        (output/'controller.log').write_bytes(run.stdout + run.stderr)
        for relative in ('silence-wire.json','silence-effects.json','silence-runtime.json'):
            (output/relative).write_bytes(read(relative))
        assert run.returncode == 0, run.stderr.decode(errors='replace')
        wire = json.loads((output/'silence-wire.json').read_bytes())
        effects = json.loads((output/'silence-effects.json').read_bytes())
        runtime = json.loads((output/'silence-runtime.json').read_bytes())
        assert runtime['patch_recipe'] == inputs['source_port/patches.py']
        messages = [event.get('message',{}) for event in wire]
        writes = [row for row in messages if row.get('id') == 'MSG_WRITE'
                  and row.get('fields',{}).get('Scope') == '1']
        notifications = [row for row in messages if row.get('id') == 'MSG_NOTIFICATION'
                         and row.get('fields',{}).get('DataType') == 'ITEM']
        checks = {}
        for dimension in ('positive','boundary','failure','recovery'):
            visible, hidden = 'COMMON_VISIBLE_' + dimension, 'COMMON_HIDDEN_' + dimension
            visible_writes = [row for row in writes if visible in json.dumps(row)]
            visible_notifications = [row for row in notifications if visible in json.dumps(row)]
            hidden_events = [row for row in writes + notifications if hidden in json.dumps(row)]
            diagnostics = [row for row in messages if row.get('id') == 'MSG_WRITE'
                and row.get('fields',{}).get('Scope') == '2' and hidden in json.dumps(row)]
            assert effects[dimension] == 42
            assert visible_writes and visible_notifications, (dimension,visible_writes,visible_notifications)
            assert not hidden_events, (dimension,hidden_events)
            if dimension in ('failure','recovery'):
                assert effects[dimension+'_error'] == 'DriverException'
                assert len(diagnostics) == 1 and diagnostics[0]['fields']['Text'].startswith('SPELL exception:')
            else:
                assert not diagnostics
            if dimension == 'boundary':
                assert any('COMMON_RESTORED_boundary' in json.dumps(row) for row in writes)
                assert any('COMMON_RESTORED_boundary' in json.dumps(row) for row in notifications)
            checks['silent-execution:'+dimension] = dict(dimension=dimension,passed=True,
                contracts=['CMP-LRM244-'+suffix for suffix in (
                    'MODIFIER-NOTIFY','MODIFIER-VERBOSITY','EXAMPLE-025','SECTION-3-6-021')],
                oracle='LRM p.31 and original SPELLexecutorImpl.C processException: no silent procedure text/item feedback; data effects and system exception diagnostics remain; default feedback resumes',
                visible_writes=visible_writes,visible_notifications=visible_notifications,
                silent_event_count=len(hidden_events),system_diagnostics=diagnostics,observed_effect=42)
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in inputs.items())
        report = dict(checks=checks,inputs=inputs,runtime_image=image,runtime_sources=runtime)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps({'evidence':str(output),'checks':len(checks),'passed':True}))
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__ == '__main__':
    main()
