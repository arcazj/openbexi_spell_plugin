"""Original native rng helpers with independent persisted-state observations."""
import json
import pathlib
import time

from spell.lang.functions import EnableRanging, DisableRanging, StartRanging, AbortRanging, StartRangingCalibration, GetBasebandNames, GetAntennaNames
from spell.stubs.SPELLDriver_pb2 import Ranging
from google.protobuf.wrappers_pb2 import BoolValue
from spell.utils.grpc_utils import UnpackValue
import hashlib
from spell.lang.constants import SKIP, REPEAT, CANCEL, ABORT
from spell.lib.exception import DriverException, SyntaxException
from spell.lib.exception import SpellException


def fixture(action, **values):
    """Request a real external manual-clock transition; never change SPELL."""
    token = str(time.monotonic_ns())
    target = pathlib.Path('fixture-request.json')
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(token=token, action=action, **values)))
    temporary.replace(target)
    reply = pathlib.Path('fixture-' + token + '.json')
    deadline = time.monotonic() + 5
    while not reply.exists():
        if time.monotonic() > deadline:
            raise TimeoutError('Fixture control did not respond')
        time.sleep(.01)
    result = json.loads(reply.read_text())
    assert 'error' not in result, result
    return result


def equal(actual, expected):
    assert actual == expected, (actual, expected)


def rejects(kind, operation):
    try:
        operation()
    except kind as error:
        return str(error)
    raise AssertionError('Expected ' + kind.__name__)


def plan_prompt(choices, answer):
    path = pathlib.Path('prompt-plans.json')
    plans = json.loads(path.read_text())
    plans.append(dict(choices=choices, answer=answer))
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(plans))
    temporary.replace(path)


CFG = dict(HandleError=False, PromptUser=False)
BBE, ANT = 'DSS-BBE-1', 'DSS-ANTENNA-1'


def mark():
    return fixture('rng_state')


def assert_effects(before, expected, state):
    after=mark()
    equal(after['ground']['ranging'],state)
    equal(after['ground']['baseband'],before['ground']['baseband'])
    delta=after['effects'][len(before['effects']):]
    equal(len(delta),len(expected))
    calls=after['rpc'][len(before['rpc']):]
    effect_calls=[r for r in calls if r['path'].rsplit('/',1)[-1] in ('EnableRanging','DisableRanging','StartRanging','StartCalibration','AbortRanging') and 'response' in r]
    equal(len(effect_calls),len(expected))
    for row,call,(method,value,bbe,antenna) in zip(delta,effect_calls,expected):
        equal(call['path'],'/spell.driver.SPELLDriverInterface_RNG/'+method)
        equal(row['state'],'RECEIPTED')
        equal(row['request_id'],call['request_id'])
        equal(row['receipt'],call['response'])
        equal(row['digest'],hashlib.sha256(call['path'].encode()+b'\0'+bytes.fromhex(call['request'])).hexdigest())
        equal(BoolValue.FromString(bytes.fromhex(row['receipt'])).value,value)
        request=Ranging.FromString(bytes.fromhex(call['request']))
        equal((request.bbe,request.antenna),(bbe,antenna))
        equal(UnpackValue(request.config),{})
    equal(len(set(r['request_id'] for r in delta)),len(delta))
    return after


def assert_no_call(before):
    after=mark()
    equal(after['effects'],before['effects'])
    equal(after['ground'],before['ground'])
    equal(after['rpc'],before['rpc'])


def assert_read(before, method, expected):
    after=mark()
    equal(after['ground'],before['ground'])
    equal(after['effects'],before['effects'])
    rows=after['rpc'][len(before['rpc']):]
    equal(len(rows),1)
    equal(rows[0]['path'],'/spell.driver.SPELLDriverInterface_RNG/'+method)
    from spell.stubs.SPELLDriver_pb2 import Names
    equal(list(Names.FromString(bytes.fromhex(rows[0]['response'])).names),expected)


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
            exec(compile(code, 'RNG:' + name, 'exec'), namespace, namespace)
            checks[name] = {'passed': True}
        except Exception as error:
            checks[name] = {'passed': False, 'error': type(error).__name__ + ': ' + str(error)}
        checks[name].update(seconds=time.monotonic() - began, source=code)
        checks[name]['expected_prompts'] = json.loads(pathlib.Path('prompt-plans.json').read_text())
        pathlib.Path('checks.json').write_text(json.dumps(checks, indent=2) + '\n')
