"""Native schedule/activity assertions with independent persistent observations."""
from rng_contracts import *


def state_effects(before, expected, activity, schedule):
    after=assert_effects(before,expected,activity)
    assert after['ground']['ranging_schedule_enabled'] is schedule
    for key,value in before['ground'].items():
        if key not in ('ranging','ranging_schedule_enabled','ranging_paths'):
            equal(after['ground'][key],value)
    paths=before['ground']['ranging_paths']
    for method,value,bbe,antenna in expected:
        if method in ('StartRanging','StartCalibration'):paths=[[bbe,antenna]]
        elif method=='AbortRanging':paths=[]
    equal(after['ground']['ranging_paths'],paths)
    return after


def check_legacy_reopen(legacy,activity,schedule):
    before=mark()
    state=dict(before['ground'])
    state.pop('ranging_schedule_enabled',None)
    state.pop('ranging_paths',None)
    state['baseband']=dict(state['baseband']);state['baseband'].pop('DSS-BBE-2',None)
    state['ranging']=legacy
    state['rng-retained-fixture']={'value':[0,False,'retained']}
    first=fixture('legacy_reopen',encoded=json.dumps(state,indent=1))
    assert first['migration_error'] is None
    expected=dict(state,ranging=activity,ranging_schedule_enabled=schedule)
    expected['baseband']=dict(state['baseband'],**{'DSS-BBE-2':{'frequency_hz':'1000000','integration_ms':'1000'}})
    expected['ranging_paths']=[[BBE,ANT]] if activity in ('RANGING','CALIBRATING') else []
    equal(first['ground'],expected)
    equal(first['effects'],before['effects'])
    equal(first['other_namespaces']['rng-unused'],' { "retain" : [0, false, 42] } ')
    second=fixture('reopen')
    assert second['migration_error'] is None
    equal(second['ground_encoded'],first['ground_encoded'])
    equal(second['ground'],expected)
    equal(GetBasebandNames(config=CFG),[BBE,'DSS-BBE-2'])


def run():
    checks = {}
    source = json.loads(pathlib.Path('cases.json').read_text())
    namespace = dict(globals())
    for name, code in source.items():
        temporary = pathlib.Path('current.tmp')
        temporary.write_text(json.dumps({'check': name}))
        temporary.replace('current.json')
        pathlib.Path('prompt-plans.json').write_text('[]')
        began = time.monotonic()
        try:
            fixture('feed', value=True)
            exec(compile(code, 'RNG_STATE:' + name, 'exec'), namespace, namespace)
            checks[name] = {'passed': True}
        except Exception as error:
            checks[name] = {'passed': False, 'error': type(error).__name__ + ': ' + str(error)}
        checks[name].update(seconds=time.monotonic() - began, source=code)
        checks[name]['expected_prompts'] = json.loads(pathlib.Path('prompt-plans.json').read_text())
        pathlib.Path('checks.json').write_text(json.dumps(checks, indent=2) + '\n')
