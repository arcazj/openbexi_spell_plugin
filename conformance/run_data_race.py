"""Qualify atomic shared compare-and-set with competing native executors."""
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
    parser.add_argument('--image',default='openbexi-spell-host:v05-data-files-native')
    args = parser.parse_args()
    output = ROOT/'.qualification/v0.5/data-race'/uuid.uuid4().hex
    output.mkdir(parents=True)
    names = ('conformance/data_race_controller.py','conformance/data_race_worker.py',
        'conformance/run_data_race.py','source_port/data_files_patches.py',
        'source_port/data_files_native_patches.py',
        'docs/reference/SPELL2.6.10-src.zip','docs/reference/SPELL - Language Reference - 2.4.4.pdf')
    names = tuple(dict.fromkeys((*names, *input_paths(ROOT))))
    inputs = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    name = 'openbexi-data-race-' + uuid.uuid4().hex
    sources = {'controller.py':(ROOT/'conformance/data_race_controller.py').read_bytes(),
        'installed_provenance.py':(ROOT/'conformance/installed_provenance.py').read_bytes(),
        'worker.py':b'import data_race_worker\n',
        'data_race_worker.py':(ROOT/'conformance/data_race_worker.py').read_bytes(),
        'setup.py':b'''from spell.lang.functions import SetSharedData
for index in range(8):
    SetSharedData(Name='race-positive-'+str(index),Value=0,HandleError=False)
SetSharedData(Name='race-boundary',Value=[],HandleError=False)
SetSharedData(Name='race-recovery',Value=0,HandleError=False)
''',
        'inspect.py':b'''import json
from pathlib import Path
from spell.lang.functions import GetSharedData
keys=['race-positive-'+str(index) for index in range(8)]+['race-boundary','race-recovery']
Path('race-final.json').write_text(json.dumps({key:GetSharedData(key,HandleError=False) for key in keys}))
'''}
    try:
        subprocess.run(['docker','create','--init','--name',name,'--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--entrypoint','python',image,'-I','/workspace/controller.py'],check=True,capture_output=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            for target,content in sources.items():
                item=tarfile.TarInfo(target)
                item.size,item.mode,item.uid,item.gid=len(content),0o644,10003,10003
                bundle.addfile(item,io.BytesIO(content))
        subprocess.run(['docker','cp','-a','-',name+':/workspace'],input=archive.getvalue(),capture_output=True,check=True)
        run = subprocess.run(['docker','start','-a',name],capture_output=True,timeout=180)
        (output/'controller.log').write_bytes(run.stdout+run.stderr)
        subprocess.run(['docker','cp',name+':/workspace',str(output/'workspace')],capture_output=True,check=True)
        assert run.returncode == 0, run.stderr.decode(errors='replace')
        left,right = [json.loads((output/f'workspace/race-result-{identity}.json').read_text()) for identity in (1,2)]
        final = json.loads((output/'workspace/race-final.json').read_text())
        checks = {}
        for dimension,keys in [('positive',['race-positive-'+str(index) for index in range(8)]),
            ('boundary',['boundary']),('failure',['failure']),('recovery',['recovery'])]:
            observations=[]
            for key in keys:
                pair = [left[key],right[key]]
                assert all(type(value) is bool for value in pair), pair
                if dimension == 'failure':
                    assert pair == [False,False],pair
                else:
                    assert sorted(pair) == [False,True],pair
                    expected = pair.index(True)+1
                    stored_key = {'boundary':'race-boundary','recovery':'race-recovery'}.get(key,key)
                    assert final[stored_key] == ([expected] if dimension == 'boundary' else expected)
                observations.append({'key':key,'executor_results':pair})
            checks['competing-executors:'+dimension] = dict(dimension=dimension,passed=True,
                contracts=['CMP-LRM244-'+suffix for suffix in ('SYNTAX-SHARED-TEST-AND-SET','SECTION-4-19-2-131')],
                oracle='LRM p.97 synchronization contract: two independent original executors in one original context race the same Expected value; exactly one succeeds, failed comparisons never win, later valid competition recovers',
                observations=observations,final_values=final)
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in inputs.items())
        report=dict(inputs=inputs,runtime_image=image,checks=checks)
        report['runtime_sources'] = json.loads((output/'workspace/race-runtime.json').read_bytes())
        verify_capture(report['runtime_sources'].get('integrated'),inputs)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'evidence':str(output),'checks':len(checks),'passed':True}))
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)


if __name__ == '__main__':
    main()
