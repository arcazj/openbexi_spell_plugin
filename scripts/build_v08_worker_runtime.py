"""Apply exact runtime dependency updates to a previously verified optimized native image."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from build_v08_native_profile import local_base
from build_v08_service_image import digest, stage


def native_files(image):
    names = ('build.json', 'bin/SPELL-Listener', 'bin/SPELL-Context', 'bin/SPELL-Executor',
             'bin/spell-host-ipc', 'bin/libspell_executor313.so')
    output = subprocess.check_output(['docker', 'run', '--rm', '--read-only', '--network=none', '--cap-drop=ALL',
        '--entrypoint', 'sha256sum', image, *('/opt/v08-native-home/' + name for name in names)], text=True)
    return {line.split(maxsplit=1)[1].strip(): line.split()[0] for line in output.splitlines()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--debs', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    pins = json.loads(args.manifest.read_bytes())
    alias, original = local_base(pins['native_image'])
    if original != pins['native_image']:
        raise ValueError('Expected the immutable native image configuration digest')
    before = native_files(original)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='openbexi-worker-updates-') as directory:
        work = Path(directory)
        stage(pins['debian'], [args.debs], work / 'debs', '.deb')
        stage(pins['wheels'], [args.wheels], work / 'wheels', '.whl')
        dockerfile = work / 'Dockerfile'
        dockerfile.write_text(f'FROM {alias}\nUSER root\nCOPY debs/ /tmp/worker-updates/debs/\n'
            'COPY wheels/ /tmp/worker-updates/wheels/\n'
            'RUN DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends install /tmp/worker-updates/debs/*.deb '
            '&& python -I -m pip install --no-index --no-deps /tmp/worker-updates/wheels/*.whl '
            '&& python -I -m pip check && rm -rf /tmp/worker-updates /var/lib/apt/lists/*\n'
            'USER 10003:10003\n', encoding='ascii')
        cmd = ['docker', 'build', '--pull=false', '--network=none', '--progress=plain', '--tag', args.tag,
               '--iidfile', str(work / 'image.id'), str(work)]
        with args.receipt.with_suffix('.log').open('wb') as output:
            subprocess.run(cmd, stdout=output, stderr=subprocess.STDOUT, check=True, timeout=600)
        image = (work / 'image.id').read_text().strip()
    if before != native_files(image):
        raise ValueError('Native binaries or the build manifest differ after applying runtime updates')
    receipt = dict(passed=True, input_image=original, image=image, tag=args.tag, manifest_sha256=digest(args.manifest),
                   unchanged_native_files=before, inputs=pins)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(image)


if __name__ == '__main__':
    main()
