"""Retain real DAP output, native child identities and complete host source maps."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import qualify_host_adapter as dap
from child_visibility_cases import CASES
from installed_provenance import input_paths

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ref=lambda p:dict(path=str(p.resolve()),sha256=sha(p))


class RetainedClient(dap.Client):
    def close(self,label):
        """Disconnect normally, retaining this task's container and transcript."""
        try:
            if self.process is not None and self.process.poll() is None:
                self.request('disconnect',terminateDebuggee=True)
                self.process.stdin.close()
                assert self.process.wait(timeout=20)==0
        finally:
            if self.process is not None and self.process.poll() is None:
                subprocess.run(['docker','stop','--time','10',self.name],capture_output=True,timeout=20)
                self.process.wait(timeout=10)
            if self.process is not None:self.thread.join(timeout=5)
            self.errors.seek(0)
            (self.project/'adapter.stderr').write_bytes(self.errors.read())
            (self.project/'transcript.json').write_text(json.dumps(self.transcript,indent=2)+'\n',encoding='utf-8',newline='\n')
            self.errors.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'.qualification/child-visibility')
    args=parser.parse_args()
    image=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    assert image==args.image
    dap.IMAGE=image
    output=args.output.resolve()/uuid.uuid4().hex;output.mkdir(parents=True)
    names=[*input_paths(ROOT),'scripts/qualify_host_adapter.py','conformance/child_visibility_cases.py',
        'conformance/run_child_visibility.py',*[p.relative_to(ROOT).as_posix() for p in (ROOT/'host_runtime/python').glob('*.py')]]
    report=dict(passed=False,runtime_image=image,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        inputs={name:sha(ROOT/name) for name in names},checks={},full_v05_accepted=False)
    def save():(output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Evidence: '+str(output),flush=True);save()
    for name,spec in CASES.items():
        project=output/name;project.mkdir()
        for path,source in {'main.py':spec['parent'],**spec['files']}.items():
            (project/path).write_text(source,encoding='utf-8',newline='\n')
        (project/'installed_provenance.py').write_bytes((ROOT/'conformance/installed_provenance.py').read_bytes())
        client=RetainedClient(project)
        row=dict(passed=False,dimension=name,container=client.name)
        try:
            client.launch('main.py',noDebug=True)
            code="import sys,json,hashlib;from pathlib import Path;sys.path.insert(0,'/workspace');from installed_provenance import capture;print(json.dumps(dict(integrated=capture(),host={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/opt/host').glob('*.py')})))"
            runtime=subprocess.check_output(['docker','exec',client.name,'python','-c',code],timeout=30)
            (project/'runtime.json').write_bytes(runtime);row['runtime']=json.loads(runtime)
            client.request('configurationDone')
            row['exit']=client.event('exited',timeout=45);client.event('terminated')
            assert row['exit']=={'exitCode':0}
            results={}
            for filename in ['parent.json',*spec['results']]:
                data=client.read_file(filename);(project/filename).write_text(data,encoding='utf-8',newline='\n')
                results[filename]=json.loads(data)
            row['results']=results
            assert results['parent.json']==spec['expected']
            console=[m['body'] for m in client.transcript if m.get('event')=='output' and m.get('body',{}).get('category')=='console']
            row['console']=console
            shown={}
            for item in console:
                source=item.get('source',{}).get('path')
                assert source
                filename=Path(source).name;shown.setdefault(filename,[]).append(item['output'])
            assert set(shown)==set(spec['shown']),(set(shown),spec['shown'])
            for filename,parts in shown.items():
                identity=results[filename.removesuffix('.py')+'.json']['instance']
                assert parts[0]=='=== SPELL child '+identity+' ===\n'
                assert ''.join(parts[1:-1])==spec['files'][filename]
                assert parts[-1]=='=== End child source ===\n'
            for filename in spec['results']:
                assert results[filename]['parent']=='main#1'
            row['passed']=True
        except Exception:row['error']=traceback.format_exc()
        finally:
            try:client.close(name)
            except Exception:row.update(passed=False,cleanup_error=traceback.format_exc())
            row['artifacts']={p.name:sha(p) for p in project.iterdir() if p.is_file()}
            report['checks'][name]=row;save()
            print(json.dumps(dict(case=name,passed=row['passed'],error=row.get('error'))),flush=True)
    report['passed']=all(row['passed'] for row in report['checks'].values());save()
    print(json.dumps(dict(output=str(output),passed=report['passed'])),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
