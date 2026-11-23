"""Build the private service image offline from a manifest of exact Debian and wheel inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stage(pins, directories, target, suffix):
    target.mkdir()
    for name, expected in pins.items():
        if Path(name).name != name or not name.endswith(suffix) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('Invalid artifact pin')
        sources = [directory / name for directory in directories if (directory / name).is_file()]
        if not sources or any(digest(path) != expected for path in sources):
            raise ValueError('Missing or mismatched artifact: ' + name)
        shutil.copyfile(sources[0], target / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--debs', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, nargs='+', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    pins = json.loads(args.manifest.read_bytes())
    dockerfile = Path(__file__).resolve().parents[1] / 'deploy/v0.8/Dockerfile.server'
    bases = re.findall(r'^FROM (python:\S+@sha256:[0-9a-f]{64})', dockerfile.read_text(), re.MULTILINE)
    if not bases or set(bases) != {pins['base_image']}:
        raise ValueError('Manifest and Dockerfile base images differ')
    if 'openbexi_spell_server-0.8.0-py3-none-any.whl' not in pins['wheels']:
        raise ValueError('The canonical server wheel is required')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='openbexi-service-') as scratch:
        context = Path(scratch)
        shutil.copyfile(dockerfile, context / 'Dockerfile')
        stage(pins['debian'], [args.debs], context / 'debs', '.deb')
        stage(pins['wheels'], args.wheels, context / 'wheels', '.whl')
        cmd = ['docker', 'build', '--pull=false', '--network=none', '--build-arg', 'SERVICE_INPUTS=staged',
               '--progress=plain', '--tag', args.tag, '--iidfile', str(context / 'image.id'), str(context)]
        with args.receipt.with_suffix('.log').open('wb') as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        image = (context / 'image.id').read_text().strip()
    probe = "import importlib.metadata as m,os,subprocess; assert os.getuid()!=0; print(m.version('openbexi-spell-server')); print(subprocess.check_output(['git','--version'],text=True).strip())"
    versions = subprocess.check_output(['docker', 'run', '--rm', '--read-only', '--network=none', '--cap-drop=ALL',
            '--entrypoint', 'python', image, '-I', '-c', probe], text=True).splitlines()
    if versions[0] != '0.8.0':
        raise ValueError('Unexpected installed service version')
    result = dict(passed=True, image=image, tag=args.tag, manifest_sha256=digest(args.manifest),
                  dockerfile_sha256=digest(dockerfile), service_version=versions[0], git=versions[1], inputs=pins)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(image)


if __name__ == '__main__':
    main()
