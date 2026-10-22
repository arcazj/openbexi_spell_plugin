"""Render the review diagrams with Graphviz and verify repeatable PNG/SVG bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    directory = Path(__file__).resolve().parents[1] / 'docs/v0.8/diagrams'
    version = subprocess.run(['dot', '-V'], capture_output=True, text=True, check=True).stderr.strip()
    report = {'renderer': version, 'repeatable': True, 'files': {}}
    for source in sorted(directory.glob('*.dot')):
        report['files'][source.name] = sha(source)
        for kind in ('png', 'svg'):
            output = source.with_suffix('.' + kind)
            subprocess.run(['dot', '-T' + kind, str(source), '-o', str(output)], check=True)
            with tempfile.TemporaryDirectory() as temporary:
                repeat = Path(temporary) / output.name
                subprocess.run(['dot', '-T' + kind, str(source), '-o', str(repeat)], check=True)
                if output.read_bytes() != repeat.read_bytes():
                    raise ValueError('Non-repeatable diagram: ' + output.name)
            report['files'][output.name] = sha(output)
    original = directory / 'v08_docker_compose.png'
    report['files'][original.name] = sha(original)
    (directory / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (directory / 'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name, digest in
                                               sorted(report['files'].items())), encoding='ascii')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
