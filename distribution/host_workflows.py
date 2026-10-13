"""Bind private real-IDE workflows to an explicit candidate runtime image.

The existing harness remains unchanged. A retained, hash-bound copy sets the
actual plugin's image setting before its Run/Debug/prompt/Stop checks. The same
private project is reopened after plugin removal. No user IDE profile is touched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--interpreter', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.qualification/v0.6/hosts')
    options = parser.parse_args()
    evidence = options.output.resolve() / uuid.uuid4().hex
    snapshot = evidence / 'source/jetbrains'
    shutil.copytree(ROOT / 'jetbrains', snapshot,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    original = snapshot / 'qualification/HostQualification.java'
    text = original.read_text(encoding='utf-8')
    anchor = 'settings.interpreter = System.getProperty("openbexi.interpreter");'
    assert text.count(anchor) == 1
    original.write_text(text.replace(anchor, anchor + '\n                '
        'settings.image = System.getenv("OPENBEXI_SPELL_QUALIFICATION_IMAGE");\n                '
        'require(settings.image != null && !settings.image.isBlank(), "Qualification image missing");'),
        encoding='utf-8', newline='\n')
    image = subprocess.check_output(['docker', 'image', 'inspect', options.image,
                                    '--format', '{{.Id}}'], text=True).strip()
    report = {'passed': False, 'image': image, 'plugin_sha256': sha(options.plugin),
              'harness_sources': {p.relative_to(snapshot).as_posix(): sha(p)
                  for p in sorted(snapshot.rglob('*')) if p.is_file()},
              'v06_release_accepted': False,
              'scope': 'Private installed actual host workflows; not noVNC visual interaction'}
    env = dict(os.environ, OPENBEXI_SPELL_QUALIFICATION_IMAGE=image)
    baseline = snapshot.parent / '.qualification/v0.3'
    try:
        for phase in ('installed', 'removed'):
            output = baseline / phase
            command = [sys.executable, str(snapshot / 'qualify.py'), '--sdk', str(options.sdk.resolve()),
                       '--plugin', str(options.plugin.resolve()), '--interpreter', str(options.interpreter.resolve()),
                       '--output', str(output)]
            if phase == 'removed':
                command += ['--remove-from', str(baseline / 'installed')]
            print('Starting private ' + phase + ' workflow: ' + str(output), flush=True)
            with (evidence / (phase + '.log')).open('w', encoding='utf-8') as log:
                subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            result_path = output / 'result.json'
            result = json.loads(result_path.read_text())
            assert result['passed'] and result['runtime_images'] == [image], result
            report[phase] = {'result': result_path.relative_to(evidence).as_posix(),
                             'sha256': sha(result_path), 'checks': result['checks'], 'sdk': result['sdk']}
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
    (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'evidence': str(evidence),
                      'error': report.get('error')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
