"""Native Notify API and modifier-compatibility oracles; no replaced runtime."""
import copy
import json
import pickle
from pathlib import Path

from spell.lang.functions import Notify, Notification, Prompt
from spell.lang.constants import ALPHA, ITEM_SUCCESS, ITEM_PROGRESS, ITEM_FAILED
from spell.lib.exception import SyntaxException
from spell.lib.adapter.config import Configurable
from spell.utils.grpc_utils import PackValue, UnpackValue

checks = {}
active = None
ROWS = ['CMP-LRM244-FUNCTION-NOTIFY', 'CMP-LRM244-EXAMPLE-109']


def equal(actual, expected):
    assert actual == expected and type(actual) is type(expected), (repr(actual), repr(expected))


def rejects(operation, kind=SyntaxException):
    try:
        operation()
    except kind:
        return
    raise AssertionError('Expected ' + kind.__name__)


def check(identifier, operation, dimension='positive', contracts=()):
    global active
    active = dict(id=identifier, items=[], prompts=[])
    row = dict(dimension=dimension, contracts=list(contracts), expected=active)
    try:
        operation()
        row['passed'] = True
    except Exception as error:
        row.update(passed=False, error=type(error).__name__ + ': ' + str(error))
    checks[identifier] = row
    Path('notification-results.json').write_text(json.dumps(dict(checks=checks), indent=2))


def notify(dimension):
    prefix = 'NOTIFY:' + active['id']
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Notify(prefix + ':missing', HandleError=False))
        rejects(lambda: Notify([[prefix, 'value']], HandleError=False))
    if dimension == 'failure':
        return
    for status in (ITEM_SUCCESS, ITEM_PROGRESS, ITEM_FAILED):
        name = prefix + ':' + status
        value = '' if dimension == 'boundary' else 'value / caf\u00e9'
        equal(Notify(name, value, status), None)
        active['items'].append(dict(ItemName=name, ItemValue=repr(value), ItemStatus=status))


def modifier_identity():
    from spell.lang.modifiers import Notify as modifier
    assert Notify is modifier and isinstance(Notify, str)
    assert str(Notify) == 'Notify' and repr(Notify) == "'Notify'"
    assert hash(Notify) == hash('Notify')
    assert {Notify: False}['Notify'] is False
    assert {'Notify': True}[Notify] is True
    for imports in (
        'from spell.lang.modifiers import *\nfrom spell.lang.functions import *',
        'from spell.lang.functions import *\nfrom spell.lang.modifiers import *',
        'from spell.runtime import *',
    ):
        namespace = {}
        exec(imports, namespace)
        assert namespace['Notify'] is Notify
    equal(json.loads(json.dumps({Notify: False})), {'Notify': False})


def validate_config(config):
    entity = Configurable()
    entity.setConfig(config)
    entity.checkConfig(globals(), locals())
    assert entity.getConfig('Notify') is False and entity.getConfig(Notify) is False


def copies():
    for config in (copy.copy({Notify: False}), copy.deepcopy({Notify: False})):
        assert next(iter(config)) is Notify
        validate_config(config)
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        config, token = pickle.loads(pickle.dumps(({Notify: False}, Notify), protocol=protocol))
        assert token is Notify and next(iter(config)) is Notify
        validate_config(config)
    equal(UnpackValue(PackValue(Notify)), 'Notify')
    config = UnpackValue(PackValue({Notify: False}))
    validate_config(config)
    assert type(next(iter(config))) is str


def strict_validation():
    class Other(str):
        pass
    custom = Other('Other')
    entity = Configurable()
    entity.setConfig({'custom': False})
    rejects(lambda: entity.checkConfig({}, {'custom': custom}))
    rejects(lambda: PackValue(custom), SyntaxError)
    rejects(lambda: Notify('invalid', HandleError=False))


def prompt(style, enabled=False):
    text = 'NOTIFY-PROMPT:' + active['id']
    answer = text + ':answer'
    active['prompts'].append(dict(text=text, answer=answer, enabled=enabled))
    Path('notification-active.json').write_text(json.dumps(active))
    config = {Notify: enabled}
    if style == 'keyword':
        result = Prompt(text, ALPHA, Notify=enabled, HandleError=False)
    elif style == 'positional':
        result = Prompt(text, ALPHA, config, HandleError=False)
    elif style == 'config':
        result = Prompt(text, ALPHA, config=config, HandleError=False)
    elif style == 'deepcopy':
        result = Prompt(text, ALPHA, config=copy.deepcopy(config), HandleError=False)
    elif style == 'pickle':
        result = Prompt(text, ALPHA, config=pickle.loads(pickle.dumps(config)), HandleError=False)
    else:
        raise AssertionError(style)
    equal(result, answer)


for dimension in ('positive', 'boundary', 'failure', 'recovery'):
    check('notify:' + dimension, lambda d=dimension: notify(d), dimension, ROWS)
check('modifier:identity', modifier_identity)
check('modifier:copies-serialization', copies)
check('modifier:strict-validation', strict_validation, 'failure')
for style in ('keyword', 'positional', 'config', 'deepcopy', 'pickle'):
    check('modifier:suppressed-' + style, lambda s=style: prompt(s))
check('modifier:enabled-recovery', lambda: prompt('config', True), 'recovery')


def legacy():
    name = 'NOTIFY:' + active['id']
    equal(Notification(name, 'legacy', ITEM_SUCCESS), None)
    active['items'].append(dict(ItemName=name, ItemValue=repr('legacy'), ItemStatus=ITEM_SUCCESS))


check('legacy:notification', legacy)
Path('notification-complete.json').write_text(json.dumps(dict(completed=True)))
