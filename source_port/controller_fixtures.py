"""Independent original-server controller procedures. SPDX-License-Identifier: GPL-3.0-or-later."""
from pathlib import Path


def write_procedures(directory: Path):
    header = "##########\n# NAME: Native controller qualification\n# SPACECRAFT: Y\n# PYTHON VERSION: 3\n##########\n"
    cases = {
        'native_controls': """import time
value = 21
checkpoint = (time.sleep(0.4), value + 1)[1]  # BREAK
skipped = 100  # SKIP
if value: raise AssertionError('Goto did not skip the guarded statement')  # GOTO_FROM
assert checkpoint == 41 and value == 40 and 'skipped' not in globals()  # GOTO_TO
with open('/out/native_controls-result.txt','w') as result:
    result.write(str(checkpoint + 1))
""",
        'native_prompt': """from spell.lang.functions import Prompt
from spell.lang.constants import YES_NO
from spell.lang.modifiers import Type
answer = Prompt('Continue qualification?',{Type:YES_NO})
assert answer is True
with open('/out/native_prompt-result.txt','w') as result:
    result.write('answered')
""",
        'native_failure': """try:
    raise ValueError('intentional controller failure')
finally:
    with open('/out/native_failure-closed.txt','w') as result:
        result.write('unwound')
""",
    }
    for name in ('native_pause', 'native_abort'):
        cases[name] = f"""import time
counter = 0
stop = False
try:
    with open('/out/{name}-ready.txt','w') as result:
        result.write('ready')
    while not stop:
        counter += 1
        time.sleep(0.02)
finally:
    with open('/out/{name}-closed.txt','w') as result:
        result.write(str(counter))
"""
    for name, body in cases.items():
        (directory / (name + '.py')).write_text(header + body)
    (directory / "native quoted ' space.py").write_text(header +
        "from pathlib import Path\nPath('/out/native_controls-quoted.txt').write_text('literal argument')\n")
    return tuple(cases)
