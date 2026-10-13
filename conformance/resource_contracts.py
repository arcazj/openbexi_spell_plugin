"""Original native resource helpers with independent persisted-state observations."""
import json
import pathlib
import time

from spell.runtime import GDB
from spell.lang.functions import GetResource, SetResource
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
            exec(compile(code, 'RESOURCE:' + name, 'exec'), namespace, namespace)
            checks[name] = {'passed': True}
        except Exception as error:
            checks[name] = {'passed': False, 'error': type(error).__name__ + ': ' + str(error)}
        checks[name].update(seconds=time.monotonic() - began, source=code)
        checks[name]['expected_prompts'] = json.loads(pathlib.Path('prompt-plans.json').read_text())
        pathlib.Path('checks.json').write_text(json.dumps(checks, indent=2) + '\n')
