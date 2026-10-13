"""Exercise installed IDE/host wheels in a fresh private Qt environment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide', type=Path, required=True)
    parser.add_argument('--ide-wheel', type=Path, required=True)
    parser.add_argument('--host-wheel', type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    evidence = ROOT / '.qualification/v0.6/openbexi' / uuid.uuid4().hex
    evidence.mkdir(parents=True)
    interpreter = evidence / ('environment/Scripts/python.exe' if os.name == 'nt' else 'environment/bin/python')
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    report = {'passed': False, 'image': image, 'ide_wheel_sha256': sha(args.ide_wheel),
              'host_wheel_sha256': sha(args.host_wheel), 'v06_release_accepted': False,
              'scope': 'Actual Qt widgets using installed wheels; offscreen, not noVNC interaction'}
    try:
        subprocess.run([sys.executable, '-m', 'venv', str(interpreter.parent.parent)], check=True)
        with (evidence / 'install.log').open('w', encoding='utf-8') as log:
            subprocess.run([str(interpreter), '-m', 'pip', 'install', '--only-binary=:all:',
                'PySide6-Essentials==6.10.3', 'debugpy==1.8.22', 'Pygments==2.21.0'],
                stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run([str(interpreter), '-m', 'pip', 'install', '--no-index', '--no-deps',
                str(args.ide_wheel.resolve())], stdout=log, stderr=subprocess.STDOUT, check=True)
        original = ROOT / 'scripts/qualify_openbexi_host.py'
        text = original.read_text(encoding='utf-8')
        anchor = "    sys.path.insert(0, str(args.ide / 'src'))"
        assert text.count(anchor) == 1
        text = text.replace(anchor, "    import openbexi_ide\n    assert Path(openbexi_ide.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())")
        anchor = "        report['image'] = subprocess.check_output(['docker', 'image', 'inspect', 'openbexi-spell-host:0.3.0', '--format', '{{.Id}}'], text=True).strip()"
        assert text.count(anchor) == 1
        text = text.replace(anchor, "        report['runtime_images'] = sorted({json.loads(path.read_text())['image'] for path in project.glob('.openbexi/runs/*/manifest.json') if 'image' in json.loads(path.read_text())})")
        adapted = evidence / 'source/scripts/qualify_openbexi_host.py'
        adapted.parent.mkdir(parents=True)
        adapted.write_text(text, encoding='utf-8', newline='\n')
        report['original_harness_sha256'] = sha(original)
        report['adapted_harness_sha256'] = sha(adapted)
        with (evidence / 'workflow.log').open('w', encoding='utf-8') as log:
            subprocess.run([str(interpreter), str(adapted), '--ide', str(args.ide.resolve()),
                '--interpreter', str(interpreter), '--wheel', str(args.host_wheel.resolve())],
                stdout=log, stderr=subprocess.STDOUT, check=True,
                env=dict(os.environ, OPENBEXI_SPELL_IMAGE=image, QT_QPA_PLATFORM='offscreen'))
        path, = (evidence / 'source/.qualification/v0.3/openbexi').glob('*/result.json')
        result = json.loads(path.read_text())
        assert result['passed'] and result['runtime_images'] == [image], result
        report.update(passed=True, checks=result['checks'], result=path.relative_to(evidence).as_posix(),
                      result_sha256=sha(path))
    except Exception as error:
        report['error'] = str(error)
    (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'evidence': str(evidence), 'error': report.get('error')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
