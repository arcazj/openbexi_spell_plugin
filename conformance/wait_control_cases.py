"""Actual IPC controls for LRM pp57-58 interrupted relative, absolute and TM waits."""
import textwrap

CASES = {}
for kind in ('relative', 'absolute', 'telemetry'):
    for action in ('step', 'skip'):
        for dimension in ('positive', 'boundary', 'failure', 'recovery'):
            name = ':'.join((kind, action, dimension))
            source = textwrap.dedent('''\
                import datetime,json,time
                from pathlib import Path
                from spell.lang.functions import WaitFor
                from spell.lang.constants import eq
                from spell.lib.exception import SyntaxException,DriverException
                CFG={'HandleError':False,'PromptUser':False}
                plan=json.loads(Path('plan.json').read_text())
                rejected=[]
                if plan['dimension']=='failure':
                    try:
                        WaitFor('+00:00:bad',config=CFG)
                    except (SyntaxException,DriverException) as error:
                        rejected.append(type(error).__name__)
                    else:
                        raise AssertionError('Invalid duration accepted')
                target=time.time()+3.2
                argument=3.2
                if plan['kind']=='absolute':
                    target=int(time.time())+4
                    argument=datetime.datetime.fromtimestamp(target,datetime.timezone.utc).strftime('%Y/%m/%d %H:%M:%S')
                if plan['kind']=='telemetry':
                    argument=['TM.CORE.TICK',eq,plan['expected_tick']]
                    CFG.update(Wait=False,Timeout=.5,Delay=10)
                Path('ready.json').write_text(json.dumps({'target':target,'started':time.monotonic(),'rejected':rejected}))
                outcome=WaitFor(argument,config=CFG)
                Path('returned.json').write_text(json.dumps({'value':outcome,'finished':time.time(),'monotonic':time.monotonic()}))
                assert outcome is True,outcome
                began=time.monotonic()
                assert WaitFor(.35,HandleError=False,PromptUser=False) is True
                elapsed=time.monotonic()-began
                assert .35<=elapsed<2,elapsed
                Path('finished.json').write_text(json.dumps({'recovery_elapsed':elapsed}))
            ''')
            compile(source, name, 'exec')
            CASES[name] = dict(kind=kind, action=action, dimension=dimension, source=source)
