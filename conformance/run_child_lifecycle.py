"""Retain actual child lifecycle observations from an owned Docker container."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import traceback
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--expect-host-rejection', action='store_true')
    group.add_argument('--externally-removed', action='store_true')
    group.add_argument('--reopen', action='store_true')
    args = parser.parse_args()
    if not args.image.startswith('sha256:') or len(args.image) != 71:
        parser.error('--image must identify the exact immutable image')
    root = Path(__file__).resolve().parent
    token = uuid.uuid4().hex
    evidence = root.parent/'.qualification/v0.6/child-lifecycle'/token
    evidence.mkdir(parents=True)
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                     '--format', '{{.Id}}'], text=True).strip()
    assert image == args.image
    name = 'openbexi-child-lifecycle-'+token
    controller = 'child_lifecycle_reopen.py' if args.reopen else 'child_lifecycle_controller.py'
    sources = [root/name for name in (controller,
               'installed_provenance.py', 'child_lifecycle_provenance.py')]
    report = dict(passed=False, image=image, container=name,
        expect_host_rejection=args.expect_host_rejection,
        externally_removed=args.externally_removed, reopen=args.reopen,
        inputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [Path(__file__), *sources]})
    created = False
    try:
        subprocess.run(['docker', 'create', '--init', '--name', name, '--network', 'none',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m', '--entrypoint', 'python', image,
            '-u', '/workspace/'+controller,
            *(['--expect-host-rejection'] if args.expect_host_rejection else []),
            *(['--externally-removed'] if args.externally_removed else [])],
            capture_output=True, check=True, timeout=20)
        created = True
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as output:
            for source in sources:
                data = source.read_bytes()
                item = tarfile.TarInfo(source.name)
                item.uid = item.gid = 10003
                item.size = len(data)
                item.mode = 0o644
                output.addfile(item, io.BytesIO(data))
        subprocess.run(['docker', 'cp', '-a', '-', name+':/workspace'], input=archive.getvalue(),
                       capture_output=True, check=True, timeout=20)
        with (evidence/'output.log').open('wb') as log:
            result = subprocess.run(['docker', 'start', '-a', name], stdout=log,
                                    stderr=subprocess.STDOUT, timeout=240)
        report['exit_code'] = result.returncode
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if created:
            try:
                content = subprocess.run(['docker', 'cp', name+':/workspace/.', '-'],
                    capture_output=True, check=True, timeout=25).stdout
                (evidence/'workspace.tar').write_bytes(content)
                report['workspace_sha256'] = hashlib.sha256(content).hexdigest()
                with tarfile.open(fileobj=io.BytesIO(content)) as archive:
                    for item in archive:
                        if item.isfile() and item.name in ('result.json', './result.json'):
                            report['observed'] = json.load(archive.extractfile(item))
            except Exception:
                report['capture_error'] = traceback.format_exc()
            try:
                subprocess.run(['docker', 'rm', '-f', name], capture_output=True,
                               check=True, timeout=25)
            except Exception:
                report['cleanup_error'] = traceback.format_exc()
        report['passed'] = (report.get('observed', {}).get('passed') is True
            and report.get('exit_code') == 0
            and not any(key.endswith('error') for key in report))
        (evidence/'result.json').write_text(json.dumps(report, indent=2)+'\n',
                                          encoding='utf-8', newline='\n')
        print(json.dumps(dict(passed=report['passed'], evidence=str(evidence))), flush=True)
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
