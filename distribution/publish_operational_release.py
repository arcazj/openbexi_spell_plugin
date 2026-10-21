"""Publish an accepted tagged release, then anonymously verify every asset."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--repository', choices=['arcazj/openbexi_spell_plugin', 'arcazj/openbexi_ide'], required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.assets.resolve()
    def git(*parts):
        return subprocess.check_output(['git', *parts], cwd=root, text=True).strip()
    commit = git('rev-parse', 'HEAD')
    assert not git('status', '--porcelain'), 'Release checkout must be clean'
    assert git('rev-parse', args.tag + '^{commit}') == commit
    assert git('ls-remote', 'origin', 'refs/heads/master').split()[0] == commit
    assert git('ls-remote', 'origin', 'refs/tags/' + args.tag + '^{}').split()[0] == commit
    record = json.loads(args.qualification.read_bytes())
    assert record['passed'] is True and record['accepted'] is True
    assert record['release'] == args.tag
    for name, expected in record['source_files'].items():
        raw = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=root)
        assert hashlib.sha256(raw).hexdigest() == expected, 'Tagged source differs: ' + name
    assets = []
    for name, row in record['artifacts'].items():
        path = output / name
        assert path.is_file() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], name
        assets.append(path)
    for source, name in [(args.notes, 'RELEASE_NOTES.md'), (args.qualification, 'QUALIFICATION.json')]:
        target = output / name
        target.write_bytes(source.read_bytes())
        assets.append(target)
    source = output / (args.repository.split('/')[-1] + '-' + args.tag + '.zip')
    subprocess.run(['git', 'archive', '--format=zip', '--prefix=' + source.stem + '/',
                    '--output=' + str(source), commit], cwd=root, check=True)
    assets.append(source)
    manifest = output / 'RELEASE_MANIFEST.json'
    manifest.write_text(json.dumps(dict(repository=args.repository, tag=args.tag, commit=commit,
        assets={p.name:dict(sha256=sha(p), bytes=p.stat().st_size) for p in assets}), indent=2) + '\n', encoding='utf-8', newline='\n')
    assets.append(manifest)
    checksums = output / 'SHA256SUMS.txt'
    checksums.write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in assets), encoding='utf-8', newline='\n')
    assets.append(checksums)
    assert len({p.name for p in assets}) == len(assets)
    assert all(p.stat().st_size < 2 * 1024 ** 3 for p in assets)
    credential = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                                capture_output=True, text=True, check=True)
    fields = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
    headers = {'Authorization':'Bearer ' + fields['password'], 'Accept':'application/vnd.github+json',
               'User-Agent':'OpenBEXI-release', 'X-GitHub-Api-Version':'2022-11-28'}
    def request(url, value=None, method=None):
        message = urllib.request.Request(url, data=None if value is None else json.dumps(value).encode(),
                                         headers={**headers, 'Content-Type':'application/json'}, method=method)
        with urllib.request.urlopen(message, timeout=120) as response:
            return json.load(response)
    api = 'https://api.github.com/repos/' + args.repository
    body = args.notes.read_text(encoding='utf-8')
    try:
        release = request(api + '/releases/tags/' + args.tag)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = request(api + '/releases', dict(tag_name=args.tag, target_commitish=commit,
                          name=args.repository.split('/')[-1] + ' ' + args.tag, draft=True,
                          prerelease=False, body=body))
    endpoint = api + '/releases/' + str(release['id'])
    existing = {a['name']:a for a in request(endpoint + '/assets?per_page=100')}
    for path in assets:
        if path.name in existing:
            asset = existing[path.name]
            assert asset['size'] == path.stat().st_size and asset.get('digest') == 'sha256:' + sha(path), path.name
            continue
        print('Uploading ' + path.name, flush=True)
        with path.open('rb') as stream:
            message = urllib.request.Request(release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(path.name),
                data=stream, headers={**headers, 'Content-Type':'application/octet-stream',
                                      'Content-Length':str(path.stat().st_size)}, method='POST')
            with urllib.request.urlopen(message, timeout=300) as response:
                asset = json.load(response)
        assert asset['size'] == path.stat().st_size and asset.get('digest') == 'sha256:' + sha(path), path.name
    release = request(endpoint, dict(draft=False, body=body, make_latest='true'), method='PATCH')
    # Publishing changes draft asset URLs. Refresh before anonymous downloads.
    remote = {a['name']:a for a in request(endpoint + '/assets?per_page=100')}
    verified = []
    for path in assets:
        asset = remote[path.name]
        digest, count = hashlib.sha256(), 0
        message = urllib.request.Request(asset['browser_download_url'], headers={'User-Agent':'OpenBEXI-release'})
        with urllib.request.urlopen(message, timeout=300) as response:
            for chunk in iter(lambda: response.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
                count += len(chunk)
        assert count == path.stat().st_size and digest.hexdigest() == sha(path), path.name
        verified.append(dict(name=path.name, sha256=digest.hexdigest(), bytes=count, url=asset['browser_download_url']))
        print('Downloaded and verified ' + path.name, flush=True)
    receipt = dict(passed=True, repository=args.repository, commit=commit, release=release['html_url'], assets=verified)
    (output / 'publication.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(passed=True, release=receipt['release'], commit=commit, assets=len(verified))), flush=True)


if __name__ == '__main__':
    main()
