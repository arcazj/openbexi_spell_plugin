"""Visible child code reaches the real DAP client; hidden code does not."""
import json

CHILD='''import json
from pathlib import Path
from spell.runtime import PROC
Path(RESULT).write_text(json.dumps({'instance':PROC['NAME'],'parent':PROC['PARENT']}))
'''
GOOD=CHILD.replace('RESULT',repr('child.json'))+'# VISIBLE_CHILD_SOURCE_MARKER\n'
HIDDEN=CHILD.replace('RESULT',repr('hidden.json'))+'# HIDDEN_CHILD_SOURCE_MARKER\n'
BAD=CHILD.replace('RESULT',repr('bad.json'))+"raise ValueError('expected child failure')\n"
PREFIX='''import json
from pathlib import Path
from spell.lang.functions import StartProc
from spell.lib.exception import DriverException
'''
CASES={
 'positive':dict(files={'child.py':GOOD},shown=['child.py'],results=['child.json'],parent=PREFIX+'''
assert StartProc('child',HandleError=False) is True
Path('parent.json').write_text(json.dumps({'returned':True}))
''',expected={'returned':True}),
 'boundary':dict(files={'hidden.py':HIDDEN},shown=[],results=['hidden.json'],parent=PREFIX+'''
assert StartProc('hidden',Visible=False,HandleError=False) is True
Path('parent.json').write_text(json.dumps({'returned':True}))
''',expected={'returned':True}),
 'failure':dict(files={'bad.py':BAD},shown=['bad.py'],results=['bad.json'],parent=PREFIX+'''
try:StartProc('bad',HandleError=False)
except DriverException:rejected=True
else:raise AssertionError('Child execution failure was accepted')
Path('parent.json').write_text(json.dumps({'rejected':rejected}))
''',expected={'rejected':True}),
 'recovery':dict(files={'child.py':GOOD,'hidden.py':HIDDEN},shown=['child.py'],results=['hidden.json','child.json'],parent=PREFIX+'''
try:StartProc('MISSING',HandleError=False,PromptUser=False)
except DriverException:rejected=True
else:raise AssertionError('Missing child was accepted')
assert StartProc('hidden',Visible=False,HandleError=False) is True
assert StartProc('child',HandleError=False) is True
Path('parent.json').write_text(json.dumps({'rejected':rejected,'recovered':True}))
''',expected={'rejected':True,'recovered':True}),
}
for name,spec in CASES.items():
    compile(spec['parent'],name,'exec')
    for path,source in spec['files'].items():compile(source,path,'exec')
