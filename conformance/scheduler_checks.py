"""Require every traced scheduler scenario; no substitution from other families."""
from scheduler_scenarios import SCENARIOS


def qualify(observations):
    checks={}
    for name,spec in SCENARIOS.items():
        result=observations.get(name,{})
        checks[name]=dict(contracts=spec['contracts'],dimension=spec['dimension'],
            passed=result.get('passed',False),
            oracle='Traced original main.py, independent UTC/monotonic target bounds and actual native WAITING/MSG_WRITE/COUNTDOWN observations.',
            dependencies=[name])
        if not checks[name]['passed']:checks[name]['error']=result.get('error','Missing native result')
    return checks,observations
