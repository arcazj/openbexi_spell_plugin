"""Capture exact Debian/Python inputs for offline toolchain reconstruction.

The supplied immutable toolchain supplies its already authenticated apt indexes.
No package versions are selected from a newly refreshed repository index.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(image):
    raw = subprocess.check_output(['docker', 'run', '--rm', '--network=none',
        '--entrypoint', 'dpkg-query', image, '-W', '-f=${binary:Package}\t${Version}\n'], text=True)
    return dict(line.split('\t') for line in raw.splitlines())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--toolchain', required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'.qualification/v06/locked-toolchain')
    args = parser.parse_args()
    output = args.output.resolve()/uuid.uuid4().hex
    output.mkdir(parents=True)
    report = dict(passed=False, base=args.base, toolchain=args.toolchain)
    print('Evidence: '+str(output), flush=True)
    try:
        for image in (args.base, args.toolchain):
            actual = subprocess.check_output(['docker', 'image', 'inspect', image,
                '--format', '{{.Id}}'], text=True).strip()
            if actual != image:
                raise ValueError('Pass immutable sha256 image identities')
        base, toolchain = inventory(args.base), inventory(args.toolchain)
        packages = {name: version for name, version in toolchain.items() if base.get(name) != version}
        (output/'packages.json').write_text(json.dumps(packages, indent=2)+'\n', encoding='utf-8')
        locks = output/'locks'
        locks.mkdir()
        for name in ('executor-build.lock', 'distribution/runtime.lock',
                     'native/continuation-requirements.txt', 'experiments/persistent-requirements.txt'):
            shutil.copyfile(ROOT/'source_port'/name, locks/Path(name).name)
        capture = output/'capture.py'
        capture.write_text('''import hashlib,json,subprocess
from pathlib import Path
root=Path('/capture');packages=json.loads((root/'packages.json').read_bytes())
debs=root/'debs';debs.mkdir()
indexes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/var/lib/apt/lists').glob('*') if p.is_file()}
(root/'apt-indexes.json').write_text(json.dumps(indexes,indent=2)+'\\n')
subprocess.run(['apt-get','download',*[name+'='+version for name,version in packages.items()]],cwd=debs,check=True)
actual={}
for p in sorted(debs.glob('*.deb')):
 fields=subprocess.check_output(['dpkg-deb','-f',str(p),'Package','Version','Architecture'],text=True)
 info=dict(line.split(': ',1) for line in fields.splitlines())
 name=info['Package'];key=name+':'+info['Architecture'] if name+':'+info['Architecture'] in packages else name
 assert key not in actual and packages[key]==info['Version'],str(p)
 actual[key]=info['Version']
assert actual==packages
wheelhouse=root/'wheelhouse';wheelhouse.mkdir()
command=['python','-m','pip','download','--require-hashes','--only-binary=:all:','--dest',str(wheelhouse)]
for lock in sorted((root/'locks').iterdir()):command.extend(['-r',str(lock)])
subprocess.run(command,check=True)
(root/'python-packages.json').write_text(subprocess.check_output(['python','-m','pip','list','--format=json'],text=True))
(root/'debian-packages.json').write_text(subprocess.check_output(['dpkg-query','-W','-f=${binary:Package}\\t${Version}\\n'],text=True))
''', encoding='utf-8', newline='\n')
        command = ['docker', 'run', '--rm', '--mount', 'type=bind,source='+str(output)+',target=/capture',
                   '--entrypoint', 'python', args.toolchain, '/capture/capture.py']
        with (output/'capture.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        report.update(passed=True, base_packages=base, toolchain_packages=toolchain,
                      additional_packages=packages, inputs={p.relative_to(output).as_posix():
                      dict(sha256=sha(p), bytes=p.stat().st_size)
                      for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'capture.log'})
    except Exception as error:
        report['error'] = type(error).__name__+': '+str(error)
    (output/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(passed=report['passed'], evidence=str(output), error=report.get('error'))), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
