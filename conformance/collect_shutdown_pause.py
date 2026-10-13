"""Recover a complete native evidence archive after Windows path extraction fails.

The original runner result and tar archive remain unchanged. This collector
requires successful native execution and verifies every retained regular file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def extended(path):
    path = path.resolve()
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    original = root / 'result.json'
    original_raw = original.read_bytes()
    report = json.loads(original_raw)
    assert report['passed'] is False and report['exit_code'] == 0
    assert report['image'].startswith('sha256:')
    archive = root / 'native-evidence.tar'
    records = {}
    with tarfile.open(archive) as bundle:
        names = set()
        for member in bundle.getmembers():
            assert member.name not in names, member.name
            names.add(member.name)
            target = (root / member.name).resolve()
            assert target.is_relative_to(root) and target != root
            target = extended(target)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                assert member.isfile(), member.name
                raw = bundle.extractfile(member).read()
                assert len(raw) == member.size
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    assert target.read_bytes() == raw, 'Conflicting previously extracted file: ' + member.name
                else:
                    target.write_bytes(raw)
                assert target.read_bytes() == raw
                records[member.name] = dict(bytes=len(raw), sha256=sha(raw))
    native = json.loads((root / 'shutdown-context-gate/result.json').read_bytes())
    assert native['passed'] and native['exit_code'] == 0
    assert native['inputs']['shutdown_pause_gate.py'] == report['inputs']['conformance/shutdown_pause_gate.py']
    for path, expected in native['outputs'].items():
        assert records['shutdown-context-gate/' + path]['sha256'] == expected
    report.update(passed=True, native=native,
                  archive=dict(sha256=sha(archive.read_bytes()), bytes=archive.stat().st_size),
                  collection_recovery=dict(reason='Windows ordinary-path extraction exceeded MAX_PATH; native exit was zero.',
                      original_report=dict(path=str(original), sha256=sha(original_raw)),
                      collector_sha256=sha(Path(__file__).read_bytes()), files=records))
    output = root / 'collected-result.json'
    assert not output.exists(), 'Preserve prior collection audit'
    output.write_text(json.dumps(report, indent=2) + '\n', newline='\n')
    assert original.read_bytes() == original_raw
    print(json.dumps({'passed': True, 'result': str(output), 'sha256': sha(output.read_bytes()), 'files': len(records)}))


if __name__ == '__main__':
    main()
