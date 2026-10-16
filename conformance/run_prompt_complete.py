"""Bounded real-DAP prompt checks, retaining native source provenance and events."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import time
import traceback
import uuid

from run_child_visibility import ROOT, RetainedClient, dap, sha
from installed_provenance import input_paths
from prompt_complete_cases import CASES


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'.qualification/prompt-complete')
    parser.add_argument('--require-timeout-metadata',action='store_true')
    args=parser.parse_args()
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    assert image==args.image;dap.IMAGE=image
    output=args.output.resolve()/uuid.uuid4().hex;output.mkdir(parents=True)
    names=[*input_paths(ROOT),'scripts/qualify_host_adapter.py','conformance/child_visibility_cases.py',
        'conformance/run_child_visibility.py','conformance/prompt_complete_cases.py',
        'conformance/run_prompt_complete.py',*[p.relative_to(ROOT).as_posix() for p in (ROOT/'host_runtime/python').glob('*.py')]]
    report=dict(passed=False,runtime_image=image,require_timeout_metadata=args.require_timeout_metadata,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        inputs={name:sha(ROOT/name) for name in names},checks={},full_v05_accepted=False)
    def save():(output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Evidence: '+str(output),flush=True);save()
    for name,spec in CASES.items():
        project=output/name.replace(':','-');project.mkdir()
        (project/'main.py').write_text(spec['source'],encoding='utf-8',newline='\n')
        (project/'installed_provenance.py').write_bytes((ROOT/'conformance/installed_provenance.py').read_bytes())
        client=RetainedClient(project);row=dict(passed=False,dimension=name.split(':')[1],container=client.name)
        try:
            client.launch('main.py',noDebug=True)
            code="import sys,json,hashlib;from pathlib import Path;sys.path.insert(0,'/workspace');from installed_provenance import capture;print(json.dumps(dict(integrated=capture(),host={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/opt/host').glob('*.py')})))"
            runtime=subprocess.check_output(['docker','exec',client.name,'python','-c',code],timeout=30)
            (project/'runtime.json').write_bytes(runtime);row['runtime']=json.loads(runtime)
            client.request('configurationDone')
            if spec.get('manual'):
                prompt=client.event('openbexi/inputRequest',timeout=10)
                if spec.get('stale'):
                    client.request('openbexi/input',promptId='invalid-'+prompt['promptId'],text='wrong',success=False)
                    row['stale_rejected']=True
                if spec['reminders']:
                    reminder=client.event('openbexi/promptReminder',timeout=3)
                    assert reminder=={k:prompt[k] for k in ('promptId','procedureId')}
                    row['reminder']=reminder
                time.sleep(spec.get('hold',.35))
                assert not any(m.get('event')=='exited' for m in client.transcript)
                assert sum(m.get('event')=='openbexi/promptReminder' for m in client.transcript)==spec['reminders']
                client.request('openbexi/input',promptId=prompt['promptId'],text='operator')
            row['exit']=client.event('exited',timeout=8);client.event('terminated')
            assert row['exit']=={'exitCode':0},row['exit']
            data=client.read_file('result.json');(project/'procedure-result.json').write_text(data,encoding='utf-8',newline='\n')
            row['results']=json.loads(data)
            prompts={m['body']['promptId']:m['body'] for m in client.transcript if m.get('event')=='spell/prompt'}
            row['prompts']=prompts
            assert len(prompts)==spec['prompts'],(len(prompts),spec['prompts'])
            reminders=[m['body'] for m in client.transcript if m.get('event')=='openbexi/promptReminder']
            row['reminders']=reminders;assert len(reminders)==spec['reminders']
            if args.require_timeout_metadata:
                for prompt in prompts.values():
                    manual=prompt['Text']=='MANUAL'
                    assert prompt['DefaultProvided']==('False' if manual else 'True'),prompt
                    assert float(prompt['TimeoutMicroseconds'])==(0 if name=='reminder:boundary' else 250000),prompt
            row['passed']=True
        except Exception:row['error']=traceback.format_exc()
        finally:
            # Save every received notification even if a baseline timeout prevents normal completion.
            row['observed_prompts']=[m['body'] for m in client.transcript if m.get('event')=='spell/prompt']
            try:client.close(name)
            except Exception:row.update(passed=False,cleanup_error=traceback.format_exc())
            row['artifacts']={p.name:sha(p) for p in project.iterdir() if p.is_file()}
            report['checks'][name]=row;save()
            print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    report['passed']=all(row['passed'] for row in report['checks'].values());save()
    print(json.dumps(dict(output=str(output),passed=report['passed'])),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
