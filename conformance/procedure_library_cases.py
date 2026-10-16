"""Original native StartProc library selection and hidden-child baselines."""
import json

CASES = {}
CONFIG = {'schema':'openbexi.spell.library/1','priorities':['Validation','Payload','Bus']}
HEADER = '''##########
# NAME: {name}
# SPACECRAFT: GENERIC
##########
'''
PARENT = '''import json
from pathlib import Path as FilePath
from spell.lang.functions import StartProc
from spell.lib.exception import DriverException
'''


def child(label, alias=None):
    header = HEADER.format(name=alias) if alias else ''
    return header+'''import json
from pathlib import Path as FilePath
from spell.runtime import ARGS
FilePath('child-started.json').write_text(json.dumps({'started':True}))
FilePath('child-result.json').write_text(json.dumps({'selected':LABEL,'arguments':{k:ARGS[k] for k in ARGS.keys()}}))
'''.replace('LABEL',repr(label))


def add(name, target, files, expected, *, options=None, args=None, configuration=None, rejection=None):
    options = options or {}
    options_text = ''.join(', '+key+'='+repr(value) for key,value in options.items())
    parent = PARENT
    if rejection:
        parent += '''try:
    StartProc(REJECT,HandleError=False,PromptUser=False)
except DriverException:
    FilePath('rejected.json').write_text(json.dumps({'rejected':True}))
else:
    raise AssertionError('Unknown child was accepted')
'''.replace('REJECT',repr(rejection))
    parent += ('result=StartProc('+repr(target)+',args='+repr(args or [])+options_text+',HandleError=False,PromptUser=False)\n'
               "FilePath('parent-result.json').write_text(json.dumps({'returned':result}))\n")
    CASES[name] = dict(parent=parent,files=files,configuration=configuration,
        expected_child={'selected':expected,'arguments':dict(args or [])},expected_parent={'returned':True},
        automatic=options.get('Automatic',True),visible=options.get('Visible',True),
        blocking=options.get('Blocking',True),rejection=bool(rejection))


add('file-identifier','child',{'child.py':child('child')},'child')
add('header-name','Friendly Procedure',{'actual_file.py':child('alias','Friendly Procedure')},'alias')
add('nested-file','Bus/procedure',{'Bus/procedure.py':child('Bus')},'Bus')
LIBRARY = {folder+'/procedure.py':child(folder) for folder in ('Bus','Payload','Validation')}
add('default-folder-order','procedure',LIBRARY,'Bus')
add('configured-priority','procedure',LIBRARY,'Validation',configuration=CONFIG)
add('configured-override','Bus/procedure',LIBRARY,'Bus',configuration=CONFIG)
add('configured-name-priority','Shared Procedure',
    {folder+'/procedure.py':child(folder,'Shared Procedure') for folder in ('Bus','Validation')},
    'Validation',configuration=CONFIG)
add('hidden-blocking','child',{'child.py':child('hidden')},'hidden',options={'Visible':False})
add('hidden-nonblocking','child',{'child.py':child('hidden')},'hidden',options={'Visible':False,'Blocking':False})
add('hidden-manual','child',{'child.py':child('hidden')},'hidden',options={'Visible':False,'Automatic':False})
add('complex-visible-manual','child',{'child.py':child('manual')},'manual',
    options={'Automatic':False,'Visible':True,'Blocking':False},args=[['A',1],['B',False],['C','']])
add('missing-then-nested','Bus/procedure',{'Bus/procedure.py':child('Bus')},'Bus',rejection='MISSING')
