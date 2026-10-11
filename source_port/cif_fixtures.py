"""Original helper/CIF integration procedures. SPDX-License-Identifier: GPL-3.0-or-later."""
from pathlib import Path


def write_procedures(directory: Path):
    header = "##########\n# NAME: Native CIF qualification\n# SPACECRAFT: Y\n# PYTHON VERSION: 3\n##########\n"
    cases = {
        'native_shared': """from spell.lang.functions import SetSharedData,GetSharedData,GetSharedDataKeys,ClearSharedData
assert SetSharedData(['native_counter',21]) is True
assert GetSharedData('native_counter')==21
assert SetSharedData(['native_counter',42]) is True
assert GetSharedData('native_counter')==42
assert 'native_counter' in GetSharedDataKeys()
assert SetSharedData(Name='native_values',Value=[True,3.5,'Unicode: \u03bb']) is True
assert GetSharedData('native_values')==[True,3.5,'Unicode: \u03bb']
ClearSharedData(['native_counter','native_values'])
assert 'native_counter' not in GetSharedDataKeys()
with open('/out/native_shared-result.txt','w') as result: result.write('roundtrip')
""",
        'native_child_parent': """from spell.lang.functions import StartProc,GetSharedData,ClearSharedData
assert StartProc('native_child',args=[['value',21]],Automatic=True,Blocking=True,Visible=False) is True
assert GetSharedData('native_child_result')==42
ClearSharedData('native_child_result')
with open('/out/native_child_parent-result.txt','w') as result: result.write('42')
""",
        'native_child': """from spell.runtime import ARGS
from spell.lang.functions import SetSharedData
assert ARGS['value']==21
assert SetSharedData(['native_child_result',ARGS['value']*2]) is True
with open('/out/native_child-result.txt','w') as result: result.write('42')
""",
        'native_wait': """import time
from spell.lang.functions import WaitFor
before=time.monotonic()
assert WaitFor(1) is True
assert time.monotonic()-before>=1.0
with open('/out/native_wait-result.txt','w') as result: result.write('waited')
""",
    }
    for name, body in cases.items():
        code=header+body
        compile(code,name+'.py','exec')
        (directory/(name+'.py')).write_text(code,encoding='utf-8')
    return ('native_shared','native_child_parent','native_wait')
