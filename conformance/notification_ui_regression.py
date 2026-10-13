"""Run unchanged UI behavioral oracles with an explicit overlay source auditor."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run():
    source = Path('ui_controller.py').read_bytes()
    old = b'from installed_provenance import capture'
    assert source.count(old) == 1
    # Only the installation auditor changes: verify the original wheel plus the
    # three checked overlay sources. Native session and every UI oracle remain
    # byte-for-byte unchanged. This is not original-wheel RECORD acceptance.
    replacement = b'''from notification_provenance import capture_notification
def capture():
    return capture_notification()['baseline']'''
    controller = source.replace(old, replacement)
    Path('ui-compat-controller.py').write_bytes(controller)
    Path('main.py').write_text('import ui_contracts\n')
    Path('edges.py').write_bytes(Path('ui_edges.py').read_bytes())
    completed = subprocess.run([sys.executable,'-I','/workspace/ui-compat-controller.py'],
        capture_output=True,timeout=750)
    Path('ui-regression.log').write_bytes(completed.stdout+completed.stderr)
    assert completed.returncode == 0, (completed.stdout+completed.stderr).decode(errors='replace')
    report = json.loads(Path('ui-results.json').read_bytes())
    wire = json.loads(Path('ui-wire.json').read_bytes())
    answers = json.loads(Path('ui-answers.json').read_bytes())
    messages = [event.get('message',{}) for event in wire]
    writes = [row['fields'] for row in messages if row.get('id') == 'MSG_WRITE' and row.get('fields',{}).get('Scope') == '1']
    items = [row['fields'] for row in messages if row.get('id') == 'MSG_NOTIFICATION' and row.get('fields',{}).get('DataType') == 'ITEM']
    for identifier, row in report['checks'].items():
        expected = row['expected']
        row['controller_answers'] = [entry for entry in answers if entry['check'] == identifier]
        row['writes'] = [entry for entry in writes if entry.get('Text','').startswith('UI:' + identifier)]
        row['items'] = [entry for entry in items if entry.get('ItemName','').startswith('UI:' + identifier)]
        try:
            assert len(row['controller_answers']) == len(expected['prompts']), 'Prompt count mismatch'
            if identifier.startswith(('display:', 'notify:')):
                assert len(row['writes']) == len(expected['writes']), 'Write count mismatch'
                assert len(row['items']) == len(expected['items']), 'Item count mismatch'
            for kind in ('writes','items'):
                for wanted in expected[kind]:
                    assert sum(all(actual.get(key)==value for key,value in wanted.items()) for actual in row[kind]) == 1, (wanted, row[kind])
        except AssertionError as error:
            row.update(passed=False,controller_error=str(error))
    report['checks'].update(json.loads(Path('ui-edge-results.json').read_bytes())['checks'])
    report['controller_source_sha256'] = hashlib.sha256(source).hexdigest()
    report['controller_with_overlay_auditor_sha256'] = hashlib.sha256(controller).hexdigest()
    report['wire'] = wire
    report['edge_wire'] = json.loads(Path('ui-edge-wire.json').read_bytes())
    Path('notification-ui-regression.json').write_text(json.dumps(report,indent=2))
