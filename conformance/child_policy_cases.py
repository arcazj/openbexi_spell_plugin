"""LRM p88: a blocking child's terminal error enters the parent's failure policy."""
CASES = {}

for outcome in ('ERROR', 'ABORTED'):
    for action in ('CANCEL', 'SKIP', 'REPEAT', 'ABORT'):
        parent = '''import json
from pathlib import Path
from spell.lang.functions import StartProc
returned = StartProc('child')
Path('first-return.json').write_text(json.dumps(returned))
recovered = StartProc('good')
assert recovered is True
Path('parent-result.json').write_text(json.dumps({'returned':returned, 'recovered':recovered}))
'''
        failure = ("raise RuntimeError('EXPECTED_CHILD_FAILURE')" if outcome == 'ERROR'
                   else "Abort('EXPECTED_CHILD_ABORT')")
        child = '''from pathlib import Path
from spell.lang.functions import Abort
attempt_file = Path('attempts.txt')
attempt = int(attempt_file.read_text()) + 1 if attempt_file.exists() else 1
attempt_file.write_text(str(attempt))
if attempt == 1:
    ''' + failure + '''
Path('child-completed.txt').write_text('finished')
'''
        good = "from pathlib import Path\nPath('recovery-completed.txt').write_text('finished')\n"
        CASES[outcome.lower() + '-' + action.lower()] = dict(
            parent=parent, child=child, good=good, action=action, outcome=outcome,
            expected_attempts=2 if action == 'REPEAT' else 1,
            expected_return=action in ('SKIP', 'REPEAT'),
            expected_parent='ABORTED' if action == 'ABORT' else 'FINISHED')
