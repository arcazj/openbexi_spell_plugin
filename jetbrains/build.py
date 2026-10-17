"""Build an installable ZIP against a specified, locally installed IntelliJ SDK."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import uuid
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def packed(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    product = json.loads((args.sdk / 'product-info.json').read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    build = args.output / ('classes-' + uuid.uuid4().hex)
    build.mkdir()
    sources = sorted((ROOT / 'src').rglob('*.java'))
    command = [str(args.sdk / 'jbr/bin/javac.exe'), '--release', '21', '-encoding', 'UTF-8',
               '-classpath', str(args.sdk / 'lib/*'), '-d', str(build), *map(str, sources)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (args.output / 'compile.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    result.check_returncode()
    entries = {p.relative_to(build).as_posix(): p.read_bytes() for p in build.rglob('*.class')}
    entries.update({p.relative_to(ROOT / 'resources').as_posix(): p.read_bytes()
                    for p in (ROOT / 'resources').rglob('*') if p.is_file()})
    entries['META-INF/LICENSE'] = (ROOT.parent / 'docs/UPSTREAM-GPL-3.0.txt').read_bytes()
    editor_exporter = ROOT.parent / 'scripts/export_spell_editor.py'
    entries['editor/export_spell_editor.py'] = editor_exporter.read_bytes()
    package = packed({'openbexi-spell/lib/openbexi-spell.jar': packed(entries)})
    version = ET.parse(ROOT / 'resources/META-INF/plugin.xml').getroot().findtext('version')
    artifact = args.output / ('openbexi-spell-' + version + '.zip')
    artifact.write_bytes(package)
    report = {'artifact': artifact.name, 'sha256': hashlib.sha256(package).hexdigest(),
        'sdk': {key: product[key] for key in ('name', 'version', 'buildNumber')},
        'inputs': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [*sources, *(ROOT / 'resources').rglob('*.xml'), Path(__file__)]},
        'status': 'Compiled candidate; verifier and actual host acceptance are separate gates'}
    report['editor_exporter_sha256'] = hashlib.sha256(editor_exporter.read_bytes()).hexdigest()
    (args.output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
