"""Execute independent conformance procedures in an exact original native image."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'scripts'))
import qualify_host_adapter as host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='openbexi-spell-host:0.3.0')
    parser.add_argument('--output',type=Path,default=ROOT/'.qualification/v0.5/time')
    args = parser.parse_args()
    output = args.output.resolve()/uuid.uuid4().hex
    project = output/'project'; project.mkdir(parents=True)
    inputs = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
        'conformance/time_contracts.py','conformance/run_native.py','conformance/inventory.json',
        'source_port/patches.py','docs/reference/SPELL - Language Reference - 2.4.4.pdf')}
    shutil.copyfile(ROOT/'conformance/time_contracts.py',project/'time_contracts.py')
    (project/'main.py').write_text("from spell.lang.functions import Display\nDisplay('TIME_CONFORMANCE_BEGIN')\nimport time_contracts\nDisplay('TIME_CONFORMANCE_END')\n",encoding='utf-8')
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    host.IMAGE,host.EVIDENCE = image,output
    client = host.Client(project)
    try:
        client.launch('main.py',noDebug=True)
        client.request('configurationDone')
        assert client.event('exited',timeout=180)['exitCode'] == 0,'Conformance harness failed; inspect transcript'
        client.event('terminated')
        report = json.loads(client.read_file('time-results.json'))
        report['runtime_image'] = image
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in inputs.items()),'Conformance inputs changed during execution'
        report['inputs'] = inputs
        inventory = json.loads((ROOT/'conformance/inventory.json').read_text(encoding='utf-8'))
        expected = {row['id'] for row in inventory['rows'] if row['package']=='TIME'}
        actual = {name for check in report['checks'].values() for name in check['contracts']}
        assert actual == expected,(expected-actual,actual-expected)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        failures = {name:row.get('error','Contained requirement failed') for name,row in report['checks'].items() if not row['passed']}
        print(json.dumps({'evidence':str(output),'checks':len(report['checks']),'failures':failures},indent=2))
        return bool(failures)
    finally:
        client.close('time-contracts')


if __name__ == '__main__':
    raise SystemExit(main())
