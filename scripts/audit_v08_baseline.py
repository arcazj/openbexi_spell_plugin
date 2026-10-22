"""Read-only v0.8 baseline audit; never changes an authority or deployment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen
import zipfile


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True, encoding='utf-8', timeout=30).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide', required=True, type=Path)
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = command(root, 'git', 'rev-parse', 'v0.7^{commit}')
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'baseline': baseline,
              'requirements_commit': command(root, 'git', 'rev-parse', 'HEAD'),
              'repository': command(root, 'git', 'remote', 'get-url', 'origin'),
              'branch': command(root, 'git', 'branch', '--show-current'),
              'remote_refs': command(root, 'git', 'ls-remote', 'origin').splitlines(),
              'local_branches': command(root, 'git', 'branch', '-v', '--no-abbrev').splitlines(),
              'worktrees': command(root, 'git', 'worktree', 'list', '--porcelain').splitlines(),
              'original_worktree': {'head': command(args.original, 'git', 'rev-parse', 'HEAD'),
                                   'status': command(args.original, 'git', 'status', '--short')},
              'ide': {'head': command(args.ide, 'git', 'rev-parse', 'HEAD'),
                      'status': command(args.ide, 'git', 'status', '--short')},
              'api': {}, 'manuals': [], 'source_inventory': {}}
    dirty = command(args.original, 'git', 'diff', '--name-only').splitlines()
    result['original_worktree']['preserved_file_sha256'] = {p: digest(args.original / p) for p in dirty}
    for name, repo, ref in [('plugin', root, baseline), ('ide', args.ide, 'HEAD')]:
        rows = command(repo, 'git', 'ls-tree', '-r', ref).splitlines()
        result['source_inventory'][name] = rows
    endpoints = {
        'repository': 'repos/arcazj/openbexi_spell_plugin',
        'release_v07': 'repos/arcazj/openbexi_spell_plugin/releases/tags/v0.7',
        'ide_release': 'repos/arcazj/openbexi_ide/releases/tags/v1.2.0',
        'open_prs': 'repos/arcazj/openbexi_spell_plugin/pulls?state=open&per_page=100',
        'workflow_runs': 'repos/arcazj/openbexi_spell_plugin/actions/runs?per_page=10',
        'commit_status': f'repos/arcazj/openbexi_spell_plugin/commits/{baseline}/status',
        'check_runs': f'repos/arcazj/openbexi_spell_plugin/commits/{baseline}/check-runs',
    }
    for key, endpoint in endpoints.items():
        request = Request('https://api.github.com/' + endpoint,
                          headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'OpenBEXI-v08-audit'})
        try:
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
            if key == 'repository':
                data = {k: data.get(k) for k in ('full_name', 'default_branch', 'html_url', 'archived', 'permissions')}
            elif key in {'release_v07', 'ide_release'}:
                data = {**{k: data[k] for k in ('tag_name', 'draft', 'prerelease', 'html_url', 'published_at')},
                        'assets': [{k: asset.get(k) for k in ('name', 'size', 'digest')} for asset in data['assets']]}
            elif key == 'open_prs':
                data = [{k: pr[k] for k in ('number', 'title', 'html_url')} for pr in data]
            result['api'][key] = {'verified': True, 'data': data}
        except Exception as error:
            result['api'][key] = {'verified': False, 'error': str(error)}
    from pypdf import PdfReader
    search = ('listener', 'context', 'executor', 'blackboard', 'monitoring', 'control mode', 'driver interface')
    for path in sorted((root / 'docs/reference').glob('*2.4.4.pdf')):
        reader = PdfReader(path)
        pages = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ''
            lowered = text.lower()
            terms = [term for term in search if term in lowered]
            if terms:
                pages.append({'pdf_page': index + 1, 'terms': terms})
                (args.output / (path.stem + f'-p{index + 1:03}.txt')).write_text(text, encoding='utf-8')
        result['manuals'].append({'file': path.relative_to(root).as_posix(), 'sha256': digest(path),
                                  'pages': len(reader.pages), 'matching_pages': pages})
    archive = root / 'docs/reference/SPELL2.6.10-src.zip'
    with zipfile.ZipFile(archive) as source:
        result['legacy_source'] = {'file': archive.relative_to(root).as_posix(), 'sha256': digest(archive),
                                   'version_caution': '2.6.10 source is not evidence of 2.4.4 wire compatibility',
                                   'architecture_files': [name for name in source.namelist()
                                       if any(term in name.lower() for term in ('listener', 'contextmanager', 'blackboard', 'ipcmessage'))
                                       and name.lower().endswith(('.cpp', '.c', '.h', '.py'))]}
        inspected = ['lib/SPELL_LST/src/SPELLlistener.C', 'lib/SPELL_CTX/src/SPELLcontext.C',
                     'lib/SPELL_CTX/src/SPELLexecutorManager.C', 'lib/SPELL_IPC/src/SPELLipcMessage.C']
        result['legacy_source']['inspected_files'] = {}
        for name in inspected:
            raw = source.read(name)
            text = raw.decode('utf-8', 'replace')
            terms = ('startExecutor', 'openExecutor', 'setExecutorController', 'startMonitorExecutor',
                     'attachProcess', 'ContextListenerPort', 'FIELD_SEQUENCE', 'hasControllingClient',
                     'removeExecutorController')
            references = [{'line': index, 'terms': [term for term in terms if term in line]}
                          for index, line in enumerate(text.splitlines(), 1) if any(term in line for term in terms)]
            result['legacy_source']['inspected_files'][name] = {
                'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'references': references}
    reports = ['V07_QUALIFICATION.json', 'V07_OPERATIONAL_PLAN.json']
    result['retained_v07_reports'] = {name: {'sha256': digest(root / 'docs' / name),
                                          'accepted': json.loads((root / 'docs' / name).read_bytes())['accepted']}
                                     for name in reports}
    result['production'] = json.loads(command(root, 'docker', 'inspect', 'openbexi-ide-spell-v07-ide-1'))[0]
    info = result['production']
    result['production'] = {'name': info['Name'], 'image': info['Image'], 'running': info['State']['Running'],
                            'health': info['State'].get('Health', {}).get('Status'),
                            'ports': info['NetworkSettings']['Ports'],
                            'mounts': [{k: mount.get(k) for k in ('Type', 'Name', 'Destination', 'RW')}
                                       for mount in info['Mounts']]}
    result['phase_a_data_collected'] = baseline == '109a47af47951e2fa54b60cb408a543b117f7f15'
    (args.output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'baseline': baseline,
                      'manuals': [{k: m[k] for k in ('file', 'pages')} for m in result['manuals']],
                      'api_verified': {k: v['verified'] for k, v in result['api'].items()},
                      'production': result['production']}), flush=True)


if __name__ == '__main__':
    main()
