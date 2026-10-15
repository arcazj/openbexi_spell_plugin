"""Diagnostic expectations from LRM pp86,88-89; no coverage promotion yet."""
CASES = {}


def case(name, *, blocking=True, automatic=True, outcome='FINISHED', hold=True, recovery=False):
    options = ('' if blocking and automatic else f', Blocking={blocking}, Automatic={automatic}')
    parent = '''import json
from pathlib import Path
from spell.lang.functions import StartProc
from spell.lib.exception import DriverException, SyntaxException
rejected=False
'''
    if recovery:
        parent += '''try:
    StartProc(['invalid'], HandleError=False)
except SyntaxException:
    rejected=True
else:
    raise AssertionError('Non-string child identifier accepted')
'''
    parent += f'''try:
    returned=StartProc('child'{options}, HandleError=False)
    result={{'returned':returned,'rejected':rejected}}
except DriverException:
    result={{'exception':'DriverException','rejected':rejected}}
Path('parent-result.json').write_text(json.dumps(result))
'''
    child = "from pathlib import Path\nPath('child-started.txt').write_text('started')\n"
    if hold:
        child += "from spell.lang.functions import Prompt\nfrom spell.lang.constants import ALPHA\nassert Prompt('CHILD_HOLD', Type=ALPHA)=='continue'\n"
    if outcome == 'ERROR':
        child += "raise RuntimeError('CHILD_EXPECTED_FAILURE')\n"
    else:
        child += "Path('child-result.txt').write_text('finished')\n"
    expected = ({'exception':'DriverException'} if blocking and outcome in {'ERROR','ABORTED'}
                else {'returned':True})
    CASES[name] = dict(parent=parent, child=child, blocking=blocking, automatic=automatic,
                       outcome=outcome, hold=hold, expected_parent={**expected, 'rejected':recovery})


case('blocking-success')
case('blocking-immediate', hold=False)
case('blocking-error', outcome='ERROR')
case('blocking-abort', outcome='ABORTED')
case('blocking-recovery', recovery=True)
case('nonblocking-success', blocking=False)
case('nonblocking-late-error', blocking=False, outcome='ERROR')
case('manual-blocking', automatic=False)
case('manual-nonblocking', blocking=False, automatic=False)
