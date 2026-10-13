"""Traced main procedure for malformed native prompt replies and recovery."""
import json
from pathlib import Path
from spell.runtime import ARGS
from spell.lang.constants import ALPHA, LIST, NUM
from spell.lang.functions import Prompt

scenario = ARGS['scenario']
kind = ARGS['kind']
ptype = {'list': LIST, 'alpha': LIST | ALPHA, 'num': LIST | NUM}[kind]
options = ['A:Option 1', 'B:Option 2'] if kind != 'num' else ['Option 1', 'Option 2']
Path('edge-entered-' + scenario).write_text('entered')
try:
    result = Prompt('UI_EDGE:' + scenario, options, Type=ptype, HandleError=False)
finally:
    Path('edge-cleanup-' + scenario).write_text('cleanup')
Path('edge-result-' + scenario).write_text(json.dumps({'result': result, 'type': type(result).__name__}))
