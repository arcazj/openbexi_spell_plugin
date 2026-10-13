"""Independent language assertions using real native SPELL and binary DSS samples."""
import json
import pathlib
import time

from spell.lang.functions import *
from spell.lang.constants import *
from spell.lang.modifiers import *
from spell.lib.adapter.tc_item import TcItemClass
from spell.lib.exception import DriverException, SyntaxException
from spell.lib.exception import SpellException
from spell.lib.adapter.utctime import TIME


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


def acquisitions():
    current = json.loads(pathlib.Path('current.json').read_text())['check']
    return [row for row in fixture('observe')['rpc']
            if row['check'] == current and row['path'].endswith('/RefreshItem')]


def acquisition_waits():
    from spell.stubs.SPELLDriver_pb2 import TmItemValue
    from spell.utils.grpc_utils import UnpackValue
    return [UnpackValue(TmItemValue.FromString(bytes.fromhex(row['request'])).config)['Wait']
            for row in acquisitions()]


def plan_prompt(choices, answer, *, raw_codes=False, contains=()):
    path = pathlib.Path('prompt-plans.json')
    plans = json.loads(path.read_text())
    plans.append(dict(choices=choices, answer=answer, raw_codes=raw_codes, contains=contains))
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(plans))
    temporary.replace(path)


def mark():
    return fixture('observe')


def fresh_setup():
    fixture('feed', value=False)
    state = fixture('tick')['state']
    fixture('tick_after_refresh', delay=.5)
    return state['core']['tick'] + 1


def fresh_assert(expected):
    from spell.stubs.SPELLDriver_pb2 import TmItemValue
    from spell.utils.grpc_utils import UnpackValue
    rows = acquisitions()
    equal(len(rows), 1)
    equal(acquisition_waits(), [True])
    equal(UnpackValue(TmItemValue.FromString(bytes.fromhex(rows[0]['response'])).engValue), expected)
    assert rows[0]['seconds'] >= .45, rows
    current = json.loads(pathlib.Path('current.json').read_text())['check']
    ticks = [row for row in mark()['controls'] if row.get('action') == 'scheduled_tick' and row['check'] == current]
    equal(len(ticks), 1)
    assert rows[0]['started'] < ticks[0]['monotonic'] <= rows[0]['started'] + rows[0]['seconds'], (rows, ticks)
    equal(ticks[0]['state']['core']['tick'], expected)


def acquisition_configs():
    from spell.stubs.SPELLDriver_pb2 import TmItemValue
    from spell.utils.grpc_utils import UnpackValue
    return [UnpackValue(TmItemValue.FromString(bytes.fromhex(row['request'])).config) for row in acquisitions()]


def effects(before, names):
    after = fixture('observe')
    rows = after['evidence']['operations'][len(before['evidence']['operations']):]
    expected = ['TRANSPORT','LOADING','RELEASE','ACKNOWLEDGEMENT','ONBOARD_EXECUTION']
    equal(len(rows),len(names)*5)
    equal(after['state']['core']['commands_executed']-before['state']['core']['commands_executed'],len(names))
    for index,name in enumerate(names):
        part=rows[index*5:(index+1)*5]
        equal([r['acknowledgement']['stage'] for r in part],expected)
        equal([r['acknowledgement']['command_name'] for r in part],[name]*5)
        assert all(r['ingress_delivery_count']==1 for r in part),part
    return rows


CFG = {HandleError:False, Confirm:False, PromptUser:False}

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
            exec(compile(code, 'SEND_VERIFY:' + name, 'exec'), namespace, namespace)
            checks[name] = {'passed': True}
        except Exception as error:
            checks[name] = {'passed': False, 'error': type(error).__name__ + ': ' + str(error)}
        checks[name].update(seconds=time.monotonic() - began, source=code)
        checks[name]['expected_prompts'] = json.loads(pathlib.Path('prompt-plans.json').read_text())
        pathlib.Path('checks.json').write_text(json.dumps(checks, indent=2) + '\n')
