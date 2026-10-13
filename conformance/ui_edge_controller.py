"""Require invalid native option replies to terminate traced procedures safely."""
import json
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, '/opt/host')
from native import NativeSession


def run():
    observations, events, checks = {}, [], {}
    for kind in ('list', 'alpha', 'num'):
        for label, answer in (('text', 'bad'), ('suffix', '1junk'), ('negative', '-1'),
                              ('past-end', '2'), ('recovery', '1')):
            scenario = kind + '-' + label
            pending = []
            session = NativeSession('/workspace', '/workspace/edges.py', dict(scenario=scenario, kind=kind))
            row = dict(answer=answer, passed=False, prompts=[])

            def drain():
                while True:
                    try:
                        event = session.events.get_nowait()
                    except queue.Empty:
                        return
                    events.append(dict(scenario=scenario, **event))
                    if event.get('event') == 'connectionError':
                        raise RuntimeError(event)
                    message = event.get('message', {})
                    if message.get('id') == 'MSG_PROMPT':
                        pending.append(message['fields'])

            try:
                session.start()
                session.pump = drain
                session.request('CMD_RUN', send=True)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    drain()
                    while pending:
                        fields = pending.pop(0)
                        assert fields['Text'] == 'UI_EDGE:' + scenario, fields
                        assert not row['prompts'], 'Unexpected repeated prompt'
                        row['prompts'].append(fields)
                        session.request('MSG_ANSWER', {'ReturnValue': answer}, send=True)
                    status = session.request('REQ_EXEC_STATUS').get('ExecutorStatus')
                    drain()
                    if status in ('FINISHED', 'ERROR', 'ABORTED'):
                        break
                    time.sleep(.02)
                else:
                    raise TimeoutError(scenario)
                row.update(status=status, entered=Path('edge-entered-' + scenario).exists(),
                    cleanup=Path('edge-cleanup-' + scenario).exists(),
                    continued=Path('edge-result-' + scenario).exists())
                assert row['entered'] and len(row['prompts']) == 1, row
                if label == 'recovery':
                    result = json.loads(Path('edge-result-' + scenario).read_text())
                    expected = {'list': 'B', 'alpha': 'Option 2', 'num': 1}[kind]
                    assert status == 'FINISHED' and row['cleanup'] and type(result['result']) is type(expected) and result['result'] == expected, (row, result)
                    row['result'] = result
                else:
                    # Original ClientIF_Prompt catches protocol core exceptions
                    # and calls executor.abort(..., true). This forced abort
                    # terminates the frame without a Python finally guarantee.
                    assert status == 'ABORTED' and not row['continued'], row
                row['passed'] = True
            except Exception as error:
                row['error'] = str(error)
            finally:
                session.close()
                row['owned_cleanup'] = True
                observations[scenario] = row
                Path('ui-edge-wire.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
                Path('ui-edge-observations.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
        contracts = {'list': ['CONSTANT-PROMPT-TYPE-LIST', 'EXAMPLE-115'],
            'alpha': ['SYNTAX-PROMPT-LIST-ALPHA', 'EXAMPLE-117'],
            'num': ['SYNTAX-PROMPT-LIST-NUM', 'EXAMPLE-116']}[kind]
        for dimension in ('failure', 'recovery'):
            selected = {name:row for name,row in observations.items()
                        if name.startswith(kind + '-') and (dimension == 'recovery' or not name.endswith('-recovery'))}
            checks['wire-' + kind + ':' + dimension] = dict(dimension=dimension,
                contracts=['CMP-LRM244-' + suffix for suffix in contracts],
                passed=all(row['passed'] for row in selected.values()), observations=selected,
                oracle='Original ClientIF_Prompt forced-abort path: malformed/out-of-range option replies terminate with no continuation; NativeSession closes owned workers; an explicit fresh executor recovers and returns the typed value with normal Python cleanup')
    Path('ui-edge-results.json').write_text(json.dumps({'checks': checks}, indent=2), encoding='utf-8')
