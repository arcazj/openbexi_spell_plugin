"""Retain an artifact- and SDK-bound Plugin Verifier invocation and verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java',type=Path,required=True)
    parser.add_argument('--verifier',type=Path,required=True)
    parser.add_argument('--plugin',type=Path,required=True)
    parser.add_argument('--sdk',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New retained evidence directory')
    args=parser.parse_args()
    root=args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    inputs={name:getattr(args,name).resolve(strict=True) for name in ('java','verifier','plugin')}
    metadata=args.sdk.resolve(strict=True)/'product-info.json'
    product=json.loads(metadata.read_bytes())
    with zipfile.ZipFile(inputs['verifier']) as archive:
        manifest=archive.read('META-INF/MANIFEST.MF').decode('utf-8')
    versions=[line.split(':',1)[1].strip() for line in manifest.splitlines() if line.startswith('Verifier-Version:')]
    if len(versions)!=1:
        raise ValueError('Verifier JAR must declare its exact version')
    report=dict(passed=False,plugin_sha256=sha(inputs['plugin']),sdk={name:product[name]
        for name in ('name','version','buildNumber','productCode')},sdk_metadata_sha256=sha(metadata),
        sdk_path=str(args.sdk.resolve()),inputs={name:dict(path=str(path),sha256=sha(path)) for name,path in inputs.items()},
        verifier_version=versions[0],harness_sha256=sha(__file__),full_v06_accepted=False)
    command=[str(inputs['java']),'-jar',str(inputs['verifier']),'check-plugin',str(inputs['plugin']),
        str(args.sdk.resolve()),'-verification-reports-dir',str(root/'reports')]
    report['command']=command
    try:
        version=subprocess.run([str(inputs['java']),'-version'],capture_output=True,check=True)
        (root/'java-version.log').write_bytes(version.stdout+version.stderr)
        with (root/'verifier.log').open('wb') as log:
            completed=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
        report['exit_code']=completed.returncode
        verdicts=list((root/'reports').rglob('verification-verdict.txt'))
        if len(verdicts)!=1:
            raise ValueError('Expected exactly one SDK/plugin verdict')
        verdict,=verdicts
        report['verdict']=dict(path=verdict.relative_to(root).as_posix(),sha256=sha(verdict))
        if completed.returncode or not verdict.read_text(encoding='utf-8').startswith('Compatible.'):
            raise ValueError('Plugin Verifier did not report compatibility')
        if any(sha(path)!=report['inputs'][name]['sha256'] for name,path in inputs.items()) or sha(metadata)!=report['sdk_metadata_sha256']:
            raise ValueError('Verifier input changed during execution')
        report['passed']=True
    except Exception:
        report['error']=traceback.format_exc()
    finally:
        report['evidence_files']={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}
        (root/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(passed=report['passed'],output=str(root))),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
