"""LRM pp.69-72: defaults, typed timeout returns and unanswered reminders."""
PREAMBLE='''import json
import time
from pathlib import Path
from spell.lang.functions import Prompt
from spell.lang.constants import ALPHA, NUM, DATE, LIST, YES_NO
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException, SyntaxException
results=[]
def auto(label, kind, default, expected, options=None):
    started=time.monotonic()
    args=[label] if options is None else [label,options]
    value=Prompt(*args,Type=kind,Default=default,Timeout=.25,HandleError=False)
    elapsed=time.monotonic()-started
    assert value==expected,(label,repr(value),repr(expected))
    assert type(value) is type(expected),(type(value),type(expected))
    assert elapsed>=.25,elapsed
    results.append(dict(label=label,value=str(value),type=type(value).__name__,elapsed=elapsed))
def invalid_timeout():
    try:Prompt('INVALID_TIMEOUT',Type=ALPHA,Default='',Timeout='invalid',HandleError=False)
    except SyntaxException:results.append(dict(rejected='timeout'))
    else:raise AssertionError('Invalid timeout accepted')
def invalid_default(kind, default):
    try:Prompt('INVALID_DEFAULT',Type=kind,Default=default,Timeout=.25,HandleError=False)
    except DriverException:results.append(dict(rejected=default))
    else:raise AssertionError('Invalid default converted')
'''
FINISH="Path('result.json').write_text(json.dumps(results))\n"


def case(body, prompts, reminders=0, **extra):
    return dict(source=PREAMBLE+body+FINISH,prompts=prompts,reminders=reminders,**extra)


MANUAL="""value=Prompt('MANUAL',Type=ALPHA,Timeout=TIMEOUT,HandleError=False)
assert value=='operator',repr(value)
results.append(dict(value=value))
"""
CASES={
    'empty-default:positive':case("auto('EMPTY',ALPHA,'','')\n",1),
    'empty-default:boundary':case("auto('EMPTY_LIST',LIST|ALPHA,'','',['','B'])\n",1),
    'empty-default:failure':case('invalid_timeout()\n',0),
    'empty-default:recovery':case("invalid_timeout()\nauto('RECOVER_EMPTY',ALPHA,'','')\n",1),
    'reminder:positive':case(MANUAL.replace('TIMEOUT','.25'),1,1,manual=True),
    'reminder:boundary':case(MANUAL.replace('TIMEOUT','0'),1,0,manual=True,hold=.6),
    'reminder:failure':case(MANUAL.replace('TIMEOUT','.25'),1,1,manual=True,stale=True),
    'reminder:recovery':case(MANUAL.replace('TIMEOUT','.25')+"auto('AFTER_REMINDER',ALPHA,'','')\n",2,1,manual=True),
    'typed-default:positive':case("auto('INTEGER',NUM,42,42)\nauto('DATE',DATE,'03-Apr-2006 09:52:34',TIME('03-Apr-2006 09:52:34'))\nauto('YES',YES_NO,'Y',True)\n",3),
    'typed-default:boundary':case("auto('ZERO',NUM,0,0)\nauto('FRACTION',NUM,-.25,-.25)\nauto('NO',YES_NO,'N',False)\n",3),
    'typed-default:failure':case("invalid_default(NUM,'not-a-number')\ninvalid_default(DATE,'not-a-date')\n",2),
    'typed-default:recovery':case("invalid_default(NUM,'invalid')\nauto('RECOVER_NUM',NUM,1,1)\nauto('LEAP_DAY',DATE,'29-Feb-2024 00:00:00',TIME('29-Feb-2024 00:00:00'))\n",3),
}
