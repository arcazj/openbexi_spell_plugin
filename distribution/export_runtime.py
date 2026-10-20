"""Export exact Docker images and verify every OCI content blob and descriptor."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    images = [subprocess.check_output(
        ['docker', 'image', 'inspect', name, '--format', '{{.Id}}'], text=True).strip()
        for name in args.image]
    archive_path = output / 'openbexi-spell-v0.6-runtime.tar.gz'
    with (output / 'docker-save.log').open('wb') as log, archive_path.open('wb') as dest:
        process = subprocess.Popen(['docker', 'image', 'save', *args.image],
                                   stdout=subprocess.PIPE, stderr=log)
        with gzip.GzipFile(filename='', mode='wb', fileobj=dest, mtime=0,
                           compresslevel=3) as compressed:
            shutil.copyfileobj(process.stdout, compressed, 1024 * 1024)
        process.stdout.close()
        assert process.wait() == 0
    blobs, documents = {}, {}
    with tarfile.open(archive_path, 'r|gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            digest, small = hashlib.sha256(), []
            with archive.extractfile(member) as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
                    if member.size < 1024 * 1024:
                        small.append(block)
            match = re.fullmatch(r'blobs/sha256/([0-9a-f]{64})', member.name)
            if match:
                assert digest.hexdigest() == match[1], member.name
                blobs[match[1]] = member.size
            if small:
                try:
                    documents[member.name] = json.loads(b''.join(small))
                except (ValueError, UnicodeError):
                    pass

    def verify(value):
        if isinstance(value, dict):
            if isinstance(value.get('digest'), str) and value['digest'].startswith('sha256:'):
                identity = value['digest'][7:]
                assert identity in blobs
                if 'size' in value:
                    assert value['size'] == blobs[identity]
            for child in value.values():
                verify(child)
        elif isinstance(value, list):
            for child in value:
                verify(child)

    for name, value in documents.items():
        if name == 'index.json' or (name.startswith('blobs/') and
                                    isinstance(value, dict) and 'schemaVersion' in value):
            verify(value)
    manifest = documents['manifest.json']
    for identity in images:
        name = 'blobs/sha256/' + identity[7:]
        assert identity[7:] in blobs and any(row['Config'] == name for row in manifest)
        config = documents[name]
        assert config['architecture'] == 'amd64' and config['os'] == 'linux'
    for row in manifest:
        assert all(layer.removeprefix('blobs/sha256/') in blobs for layer in row['Layers'])
    result = dict(passed=True, images=images, requested_images=args.image,
                  archive=dict(path=str(archive_path), sha256=sha(archive_path),
                               bytes=archive_path.stat().st_size),
                  descriptor_graph_verified=True, verified_content_blobs=len(blobs),
                  harness_sha256=sha(Path(__file__)))
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n',
                                      encoding='utf-8', newline='\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
