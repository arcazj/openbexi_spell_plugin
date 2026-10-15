"""Build an explicitly diagnostic child lifecycle image with retained inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASES = {
    'NATIVE_BASE': ('openbexi-spell-native:v06-checkpoint-audit-059395',
        'sha256:b29d925842949f84f26ad2fb0dd51624dc17e021e76e5c911a1f61b179660235'),
    'RUNTIME_BASE': ('openbexi-spell-dss:v06-child-client-development',
        'sha256:b7c4cd03377ff1f9e010621caf4cc1ac2dd140d7b08099fb88de98f21823cef5'),
}


def image_id(tag):
    return subprocess.check_output(['docker', 'image', 'inspect', tag,
        '--format', '{{.Id}}'], text=True, timeout=20).strip()


def main():
    token = uuid.uuid4().hex
    evidence = ROOT/'.qualification/v0.6/child-lifecycle-build'/token
    evidence.mkdir(parents=True)
    paths = [*sorted((ROOT/'conformance').glob('*child_lifecycle*')),
        ROOT/'source_port/child_lifecycle_patches.py',
        ROOT/'distribution/incremental_native.py',
        ROOT/'host_runtime/native_bridge.cpp', ROOT/'host_runtime/build_bridge.py',
        ROOT/'conformance/installed_provenance.py']
    inputs = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in paths if p.is_file()}
    report = dict(passed=False, inputs=inputs, bases=BASES, full_v06_accepted=False)
    tag = 'openbexi-spell-dss:v06-child-lifecycle-'+token[:12]
    native_tag = 'openbexi-spell-native:v06-child-lifecycle-'+token[:12]
    try:
        for base, expected in BASES.values():
            assert image_id(base) == expected
        command = ['docker', 'build', '--progress', 'plain', '--network=none']
        for key, (base, _) in BASES.items():
            command += ['--build-arg', key+'='+base]
        command += ['-f', 'conformance/child_lifecycle.Dockerfile']
        report['commands'] = []
        for target, options in ((tag, []), (native_tag, ['--target', 'native'])):
            invocation = [*command, *options, '-t', target, '.']
            report['commands'].append(invocation)
            with (evidence/(('native' if options else 'runtime')+'-build.log')).open('wb') as log:
                completed = subprocess.run(invocation, cwd=ROOT, stdout=log,
                                           stderr=subprocess.STDOUT, timeout=300)
            if completed.returncode:
                raise RuntimeError('Diagnostic image build failed: '+target)
        report.update(image=image_id(tag), native_image=image_id(native_tag))
        for base, expected in BASES.values():
            assert image_id(base) == expected
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == value
                   for name, value in inputs.items())
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    report['logs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in evidence.glob('*.log')}
    (evidence/'result.json').write_text(json.dumps(report, indent=2)+'\n',
                                      encoding='utf-8', newline='\n')
    print(json.dumps(dict(evidence=str(evidence), **report)), flush=True)
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
