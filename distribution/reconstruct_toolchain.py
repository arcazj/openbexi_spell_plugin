"""Reconstruct locked build and compiler-free runtime images without network."""
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


def output(command):
    return subprocess.check_output(command, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'.qualification/v06/offline-inputs')
    args = parser.parse_args()
    evidence = args.output.resolve()/uuid.uuid4().hex
    context = evidence/'source'
    context.mkdir(parents=True)
    result = dict(passed=False, network='none', cache=False)
    print('Evidence: '+str(evidence), flush=True)
    try:
        capture = args.capture.resolve()
        record = json.loads((capture/'result.json').read_bytes())
        assert record['passed']
        for name, info in record['inputs'].items():
            assert sha(capture/name) == info['sha256'], name
        result['capture_sha256'] = sha(capture/'result.json')
        base = record['base']
        assert output(['docker','image','inspect',base,'--format','{{.Id}}']) == base
        base_tag = 'openbexi-locked-base:'+base.split(':')[1][:16]
        subprocess.run(['docker','tag',base,base_tag],check=True)
        for name in ('debs','wheelhouse','locks'):
            shutil.copytree(capture/name,context/name)
        shutil.copyfile(capture/'packages.json',context/'packages.json')
        installer = '''import hashlib,json,subprocess,sys
from pathlib import Path
root=Path('/locked');mode=sys.argv[1]
packages=json.loads((root/'packages.json').read_bytes())
if mode=='build':
 subprocess.run(['dpkg','--install',*[str(p) for p in sorted((root/'debs').glob('*.deb'))]],check=True)
else:
 index=[]
 for p in sorted((root/'debs').glob('*.deb')):
  fields=subprocess.check_output(['dpkg-deb','-f',str(p)],text=True)
  index.append(fields+'Filename: ./'+p.name+'\\nSize: '+str(p.stat().st_size)+'\\nSHA256: '+hashlib.sha256(p.read_bytes()).hexdigest()+'\\n')
 (root/'debs/Packages').write_text('\\n'.join(index))
 (root/'sources.list').write_text('deb [trusted=yes] file:/locked/debs ./\\n')
 opts=['-o','Dir::Etc::sourcelist=/locked/sources.list','-o','Dir::Etc::sourceparts=-','-o','Dir::State::lists=/locked/lists']
 (root/'lists/partial').mkdir(parents=True)
 subprocess.run(['apt-get',*opts,'update'],check=True)
 names=['libasan8:amd64','libubsan1:amd64','libxerces-c3.2t64:amd64','liblog4cplus-2.0.5t64:amd64','libncurses6:amd64']
 subprocess.run(['apt-get',*opts,'install','-y','--no-install-recommends',*[name+'='+packages[name] for name in names]],check=True)
locks=['runtime.lock'] if mode=='runtime' else ['executor-build.lock','continuation-requirements.txt','persistent-requirements.txt']
command=['python','-m','pip','install','--no-index','--find-links=/locked/wheelhouse','--require-hashes','--only-binary=:all:']
for lock in locks:command.extend(['-r',str(root/'locks'/lock)])
subprocess.run(command,check=True)
'''
        (context/'install.py').write_text(installer,encoding='utf-8',newline='\n')
        result['images'] = {}
        for mode in ('build','runtime'):
            recipe = context/(mode+'.Dockerfile')
            recipe.write_text('''ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN --mount=type=bind,target=/inputs cp -a /inputs /locked && python /locked/install.py '''+mode+''' && mkdir /wheelhouse /toolchain && cp /locked/wheelhouse/* /wheelhouse/ && dpkg-query -W > /toolchain/debian-packages.txt && python -m pip freeze --all > /toolchain/python-packages.txt && rm -rf /locked /root/.cache/pip
'''+('RUN c++ --version > /toolchain/compiler.txt\n' if mode=='build' else
'''RUN rm -f /wheelhouse/grpcio_tools-* /wheelhouse/setuptools-*
RUN python -c "import shutil,importlib.util; assert all(shutil.which(n) is None for n in ('gcc','g++','cc','c++','gdb','protoc')); assert importlib.util.find_spec('grpc_tools') is None"
'''),encoding='utf-8',newline='\n')
            tag = 'openbexi-spell-'+mode+':v06-locked-'+evidence.name[:12]
            with (evidence/(mode+'.log')).open('w',encoding='utf-8') as log:
                subprocess.run(['docker','build','--no-cache','--network=none','--progress=plain',
                    '--build-arg','BASE_IMAGE='+base_tag,'-f',str(recipe),'-t',tag,str(context)],
                    stdout=log,stderr=subprocess.STDOUT,check=True)
            image = output(['docker','image','inspect',tag,'--format','{{.Id}}'])
            raw = output(['docker','run','--rm','--network=none','--entrypoint','dpkg-query',image,'-W','-f=${binary:Package}\t${Version}\n'])
            packages = dict(line.split('\t') for line in raw.splitlines())
            if mode=='build':
                assert packages==record['toolchain_packages'], 'Reconstructed Debian inventory differs'
            else:
                allowed = dict(record['base_packages'],**record['toolchain_packages'])
                assert all(allowed.get(k)==v for k,v in packages.items()), 'Uncaptured runtime dependency'
            python = json.loads(output(['docker','run','--rm','--network=none','--entrypoint','python',image,'-m','pip','list','--format=json']))
            if mode=='build':
                assert python==json.loads((capture/'python-packages.json').read_bytes()), 'Python inventory differs'
            result['images'][mode] = dict(tag=tag,image=image,debian=packages,python=python)
        result.update(passed=True,base=base,inputs={p.relative_to(context).as_posix():sha(p) for p in sorted(context.rglob('*')) if p.is_file()})
    except Exception as error:
        result['error'] = type(error).__name__+': '+str(error)
    (evidence/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'],evidence=str(evidence),error=result.get('error'))),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
