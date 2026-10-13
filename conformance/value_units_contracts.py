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

def argument(value, modifiers=None, name='ARG1', command='CMDNAME'):
    item = BuildTC(command,args=[[name,value,modifiers or {}]],config=CFG)
    equal(len(item._getParams()),1)
    return item,item._getParams()[0].value


def exact(value, expected, vtype):
    actual=value.get()
    assert type(actual) is type(expected),(type(actual),type(expected),actual,expected)
    equal(actual,expected)
    equal(value.vtype(),vtype)
    equal(value.format(),ENG)
    equal(value.radix(),DEC)
    return value


def sends_since(before):
    return [row for row in fixture('observe')['rpc'][len(before['rpc']):]
            if row['path'].endswith('/SendCommand')]


def no_send(before):
    equal(sends_since(before),[])
    effects(before,[])


def wire_argument(before,expected,kind):
    from spell.stubs.SPELLDriver_pb2 import CommandDesc
    from spell.utils.grpc_utils import UnpackValue
    calls=sends_since(before)
    equal(len(calls),1)
    request=CommandDesc.FromString(bytes.fromhex(calls[0]['request']))
    arguments=UnpackValue(request.args)
    equal(len(arguments),1)
    assert type(arguments[0][1]) is type(expected)
    equal(arguments[0][1],expected)
    equal(arguments[0][2]['ValueType'],kind)


def sent_argument(before, item, expected, kind, name='ARG1'):
    assert Send(command=item,config=CFG) is True
    rows=effects(before,[item.name()])
    equal(len(sends_since(before)),1)
    result=mark()['state']['core']['last_command_arguments']
    entry=next(row for row in result if row['name']==name)
    assert type(entry['value']) is type(expected),(entry,expected)
    equal(entry['value'],expected)
    equal(entry['value_type'],kind)
    return entry


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
            exec(compile(code, 'VALUE_UNITS:' + name, 'exec'), namespace, namespace)
            checks[name] = {'passed': True}
        except Exception as error:
            checks[name] = {'passed': False, 'error': type(error).__name__ + ': ' + str(error)}
        checks[name].update(seconds=time.monotonic() - began, source=code)
        checks[name]['expected_prompts'] = json.loads(pathlib.Path('prompt-plans.json').read_text())
        pathlib.Path('checks.json').write_text(json.dumps(checks, indent=2) + '\n')
