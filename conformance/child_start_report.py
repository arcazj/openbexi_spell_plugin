"""Verify failed child loads and same-parent recovery before reviewing coverage."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from child_start_cases import CASES
from installed_provenance import verify_capture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution'))
from run_language_regressions import validate_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(path, image):
    raw = json.loads(path.read_bytes())
    validate_report(path, image, len(CASES))
    assert raw['passed'] and not raw['timed_out']
    assert set(raw['checks']) == set(CASES)
    captured = raw['runtime_sources']['integrated']
    assert captured is not None
    verify_capture(captured, raw['inputs'])
    assert raw['host_inputs'] == {p.name: sha(p) for p in (ROOT / 'host_runtime/python').glob('*.py')}
    for name, spec in CASES.items():
        row = raw['checks'][name]
        assert row['source'] == spec['parent'] and row['child_source'] == spec['child'], name
        assert row['rejection']['exception'] == 'DriverException' and row['rejection']['message'], name
        assert row['parent_status'] == 'FINISHED' and row['result'] == spec['expected'], name
        assert row['result']['rejected'] is True, name
        assert not any(key.endswith('_error') for key in row), name
        project = path.parent / 'workspace' / name
        for file, expected in (('main.py', spec['parent']), ('child.py', spec['child'])):
            assert (project / file).read_text(encoding='utf-8') == expected, name
        for file, key in (('events.json', 'events_sha256'), ('native.log', 'native_log_sha256')):
            assert sha(project / file) == row[key], name
        assert json.loads((project / 'failed-start.json').read_bytes()) == row['rejection'], name
        assert json.loads((project / 'parent-result.json').read_bytes()) == row['result'], name
        events = json.loads((project / 'events.json').read_bytes())
        opened = {event['message']['fields']['ProcId'] for event in events
                  if event.get('message', {}).get('id') == 'MSG_EXEC_OP'
                  and event['message']['fields'].get('ExecOp') == 'OPEN'
                  and event['message']['fields'].get('ParentId') == row['parent_instance']}
        assert not any(event.get('event') in {'connectionError', 'unsupportedRequest', 'childRequestRejected'}
                       for event in events), name
        expected = {row['parent_instance']}
        if spec['recovery']:
            assert row['result']['returned'] is True, name
            assert row['child_status'] == 'FINISHED', name
            assert (project / 'child-finished.txt').read_text(encoding='utf-8') == 'finished', name
            assert opened == {row['child_instance']}, name
            expected |= opened
            mode = '{Automatic:%s,Visible:True,Blocking:%s}' % (spec['automatic'], spec['blocking'])
            assert row['child_info']['OpenMode'] == mode, name
            if not spec['automatic']:
                assert len(row['observations']) == 3, name
                for state in row['observations']:
                    assert state['child_status'] == 'PAUSED' and not state['child_finished'], name
                    assert state['parent_returned'] is (not spec['blocking']), name
            else:
                assert row['observations'] == [], name
        else:
            assert not opened and row['observations'] == [], name
            assert not (project / 'child-finished.txt').exists(), name
            assert 'child_instance' not in row and 'child_status' not in row, name
        assert set(filter(None, row['inventory']['ExecutorList'].split('\x03'))) == expected, name
    report = deepcopy(raw)
    report.update(raw={'path': str(path.resolve()), 'sha256': sha(path)}, qualified_contracts=[],
        scope='Eight failed-load and same-parent recovery controls across all automatic/blocking combinations; coverage mapping requires separate review.',
        full_v05_accepted=False, full_v06_accepted=False)
    report['inputs']['conformance/child_start_report.py'] = sha(Path(__file__))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    report = qualify(args.raw, args.image)
    path = ROOT / 'conformance/evidence/child_start.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': str(path), 'checks': len(report['checks']), 'contracts': 0}))


if __name__ == '__main__':
    main()
