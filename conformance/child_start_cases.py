"""Missing-procedure failure and subsequent valid startup in all four modes."""
CASES = {}
for automatic in (True, False):
    for blocking in (True, False):
        for recovery in (False, True):
            name = f'automatic-{automatic}-blocking-{blocking}-' + ('recovery' if recovery else 'failure')
            options = f'Automatic={automatic}, Blocking={blocking}, HandleError=False'
            parent = f'''import json
from pathlib import Path
from spell.lang.functions import StartProc
from spell.lib.exception import DriverException
try:
    StartProc('not_installed_child', {options})
except DriverException as error:
    rejected={{'exception':type(error).__name__, 'message':str(error)}}
else:
    raise AssertionError('Missing child procedure accepted')
Path('failed-start.json').write_text(json.dumps(rejected))
'''
            if recovery:
                parent += f"returned=StartProc('child', {options})\nassert returned is True\n"
                parent += "Path('parent-result.json').write_text(json.dumps({'rejected':True,'returned':returned}))\n"
            else:
                parent += "Path('parent-result.json').write_text(json.dumps({'rejected':True}))\n"
            CASES[name] = dict(automatic=automatic, blocking=blocking, recovery=recovery,
                parent=parent, child="from pathlib import Path\nPath('child-finished.txt').write_text('finished')\n",
                expected={'rejected':True, **({'returned':True} if recovery else {})})
