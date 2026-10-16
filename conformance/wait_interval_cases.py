"""Scaled real-clock controls for LRM pp58-59 simple and staged progress."""
import textwrap

CASES={}
for family in ('simple','complex'):
    for dimension in ('positive','boundary','failure','recovery'):
        name=family+':'+dimension
        # Give the native 200ms scheduler and acknowledged IPC room to show
        # repeated updates in every phase, including the shortest interval.
        duration=8.0 if family=='simple' else 30.0
        interval=2 if family=='simple' else [15,5,1]
        if dimension=='boundary':duration,interval=.35,(.5 if family=='simple' else [.5])
        source=textwrap.dedent('''\
            import json,time
            from pathlib import Path
            from spell.lang.functions import WaitFor
            from spell.lib.exception import SyntaxException,DriverException
            plan=json.loads(Path('plan.json').read_text())
            rejected=[]
            if plan['dimension'] in ('failure','recovery'):
                try:
                    WaitFor(.1,Interval=1,Message='',HandleError=False,PromptUser=False)
                except (SyntaxException,DriverException) as error:
                    rejected.append(type(error).__name__)
                else:
                    raise AssertionError('Interval without progress message accepted')
            result={'rejected':rejected}
            if plan['dimension']!='failure':
                began=time.monotonic()
                Path('ready.json').write_text(json.dumps({'started':began}))
                outcome=WaitFor(plan['duration'],Interval=plan['interval'],Message=plan['message'],
                    HandleError=False,PromptUser=False)
                ended=time.monotonic()
                assert outcome is True
                assert plan['duration']<=ended-began<plan['duration']+1
                result.update(started=began,ended=ended,returned=outcome)
            Path('result.json').write_text(json.dumps(result))
        ''')
        compile(source,name,'exec')
        CASES[name]=dict(source=source,family=family,dimension=dimension,duration=duration,
            interval=interval,message='INTERVAL:'+name,waiting=dimension!='failure')
