"""LRM pp.68,70-72 oracles executed by the original native executor.

The controller supplies actual IPC answers and independently inspects messages.
No registry, helper, CIF or executor methods are replaced.
"""
import json
from pathlib import Path

from spell.lang.constants import (
    ALPHA, CANCEL, DATE, ERROR, INFORMATION, ITEM_FAILED, ITEM_PROGRESS,
    ITEM_SUCCESS, LIST, NO, NUM, OK, OK_CANCEL, WARNING, YES, YES_NO,
)
from spell.lang.functions import Display, Notification, Prompt
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import DriverException, SyntaxException

PREFIX = 'CMP-LRM244-'
checks = {}
active = None


def equal(actual, expected):
    assert type(actual) is type(expected) and actual == expected, (repr(actual), repr(expected))


def rejects(operation, kind=SyntaxException):
    try:
        operation()
    except kind as error:
        return type(error).__name__
    raise AssertionError('Expected ' + kind.__name__)


def prompt(ptype, answer, choices, expected, *, options=None, **config):
    text = 'UI:' + active['id'] + ':' + str(len(active['prompts']))
    active['prompts'].append(dict(text=text, answer=answer, choices=choices))
    Path('ui-active.json').write_text(json.dumps(active), encoding='utf-8')
    result = Prompt(text, ptype, HandleError=False, **config) if options is None else Prompt(
        text, options, Type=ptype, HandleError=False, **config)
    if isinstance(expected, TIME):
        assert isinstance(result, TIME) and result.isAbs() and result.abs() == expected.abs(), repr(result)
    else:
        equal(result, expected)


def check(name, contracts, dimension, operation, oracle):
    global active
    identifier = name + ':' + dimension
    active = dict(id=identifier, prompts=[], writes=[], items=[])
    Path('ui-active.json').write_text(json.dumps(active), encoding='utf-8')
    row = dict(contracts=[PREFIX + item for item in contracts], dimension=dimension, oracle=oracle)
    try:
        operation()
        row['passed'] = True
    except Exception as error:
        row.update(passed=False, error=type(error).__name__ + ': ' + str(error))
    row['expected'] = active
    checks[identifier] = row
    Path('ui-results.json').write_text(json.dumps(dict(checks=checks), indent=2), encoding='utf-8')


def message(dimension):
    prefix = 'UI:display:' + dimension
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Display(prefix + ':invalid', 99999, HandleError=False))
    if dimension == 'failure':
        return
    for number, severity, level in ((0, INFORMATION, 'INFO'), (1, WARNING, 'WARN'), (2, ERROR, 'ERROR')):
        text = prefix + ':' + str(number) + ('\nsecond line: café' if dimension == 'boundary' else '')
        config = {} if number == 0 else dict(Severity=severity)
        equal(Display(text, **config), None)
        active['writes'].append(dict(Text=text, Level=level, Scope='1'))
    if dimension == 'boundary':
        equal(Display(prefix + ':positional', WARNING), None)
        active['writes'].append(dict(Text=prefix + ':positional', Level='WARN', Scope='1'))


def notification(dimension):
    prefix = 'UI:notify:' + dimension
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Notification(prefix + ':invalid', HandleError=False))
        rejects(lambda: Notification([[prefix, 'value']], HandleError=False))
    if dimension == 'failure':
        return
    for status in (ITEM_SUCCESS, ITEM_PROGRESS, ITEM_FAILED):
        name = prefix + ':' + status
        value = '' if dimension == 'boundary' else '42'
        equal(Notification(name, value, status), None)
        # Original native ITEM serializes the typed string using Python repr.
        active['items'].append(dict(ItemName=name, ItemValue=repr(value), ItemStatus=status))


for dimension in ('positive', 'boundary', 'failure', 'recovery'):
    check('display', ['FUNCTION-DISPLAY', 'EXAMPLE-108', 'SECTION-4-9-082',
        'CONSTANT-SEVERITY-INFORMATION', 'CONSTANT-SEVERITY-WARNING', 'CONSTANT-SEVERITY-ERROR'],
        dimension, lambda d=dimension: message(d),
        'LRM p.68: Display emits procedure text at default INFO or explicit WARN/ERROR, returns None; invalid positional severity emits no procedure message; a later valid call succeeds')
    check('notify', ['CONSTANT-ITEM-STATUS-ITEM-SUCCESS',
        'CONSTANT-ITEM-STATUS-ITEM-PROGRESS', 'CONSTANT-ITEM-STATUS-ITEM-FAILED'],
        dimension, lambda d=dimension: notification(d),
        'LRM p.68: NAME/VALUE/status notifications reach actual native ITEM messages; empty values survive, malformed argument lists fail without item effects, later valid notifications succeed')


for label, ptype, choices, values in (
    ('OK', OK, ['O'], [True]), ('CANCEL', CANCEL, ['C'], [False]),
    ('YES', YES, ['Y'], [True]), ('NO', NO, ['N'], [False]),
    ('YES-NO', YES_NO, ['Y', 'N'], [True, False]),
    ('OK-CANCEL', OK_CANCEL, ['O', 'C'], [True, False]),
):
    def operation(dimension, ptype=ptype, choices=choices, values=values):
        if dimension in ('failure', 'recovery'):
            rejects(lambda: Prompt(123, ptype, HandleError=False))
            rejects(lambda: Prompt('UI:invalid-timeout', ptype, Timeout='bad', HandleError=False))
        if dimension != 'failure':
            index = len(values)-1 if dimension == 'boundary' else 0
            prompt(ptype, str(index), choices, values[index])
    for dimension in ('positive', 'boundary', 'failure', 'recovery'):
        rows = ['CONSTANT-PROMPT-TYPE-' + label]
        if label == 'OK':
            rows.append('EXAMPLE-114')
        check('prompt-' + label.lower(), rows, dimension, lambda d=dimension: operation(d),
            'LRM pp.70-71 and original CIF Boolean conversion: exact native choices and Boolean result; last option and singleton boundaries; invalid message/timeout rejected before prompt; explicit later prompt succeeds')


def text_prompt(dimension):
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Prompt(None, ALPHA, HandleError=False))
    if dimension != 'failure':
        value = '' if dimension == 'boundary' else 'alpha 42 / café'
        prompt(ALPHA, value, [], value)


def number_prompt(dimension):
    if dimension in ('failure', 'recovery'):
        # Invalid numeric input reaches the native CIF conversion, not a fake helper.
        rejects(lambda: prompt(NUM, 'not-a-number', [], 0), DriverException)
    if dimension != 'failure':
        for answer, expected in ([('-0.25', -0.25), ('0', 0), ('1e3', 1000.0),
                ('1E3', 1000.0), ('1e-3', 0.001), ('1E+3', 1000.0)]
                if dimension == 'boundary' else [('42', 42)]):
            prompt(NUM, answer, [], expected)


def date_prompt(dimension):
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Prompt('UI:invalid-date-timeout', DATE, Timeout=TIME('03-Apr-2006 09:52:34'), HandleError=False))
        rejects(lambda: prompt(DATE, 'not-a-date', [], TIME('03-Apr-2006 09:52:34')), DriverException)
        rejects(lambda: prompt(DATE, "2000/01/01') if False else 17 #", [], TIME('03-Apr-2006 09:52:34')), DriverException)
        rejects(lambda: prompt(DATE, '1', [], TIME('03-Apr-2006 09:52:34')), DriverException)
    if dimension != 'failure':
        value = '29-Feb-2000 00:00:00' if dimension == 'boundary' else '03-Apr-2006 09:52:34'
        prompt(DATE, value, [], TIME(value))


def list_prompt(dimension, alpha=False, numeric=False):
    ptype = LIST | (ALPHA if alpha else NUM if numeric else 0)
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Prompt('UI:empty-list', [], Type=ptype, HandleError=False))
    if dimension != 'failure':
        options = ['Option 1', 'Option 2'] if alpha or numeric else ['A:Option 1', 'B:Option 2']
        choices = options if alpha else ['1', '2'] if numeric else ['A', 'B']
        index = 1 if dimension == 'boundary' else 0
        expected = options[index] if alpha else index if numeric else choices[index]
        prompt(ptype, str(index), choices, expected, options=options)
        if alpha:
            prompt(ptype, str(index), ['Option 1', 'Option 2'], options[index],
                   options=['A:Option 1', 'B:Option 2'])


for name, contracts, operation, oracle in (
    ('alpha', ['CONSTANT-PROMPT-TYPE-ALPHA'], text_prompt, 'LRM p.70: free text including empty and UTF-8 values; invalid message fails; later valid prompt succeeds'),
    ('num', ['CONSTANT-PROMPT-TYPE-NUM'], number_prompt, 'LRM p.70: integer, fractional and zero answers are numbers; invalid native conversion fails; later valid prompt succeeds'),
    ('date', ['CONSTANT-PROMPT-TYPE-DATE'], date_prompt, 'LRM p.70: date answers become absolute TIME including leap day; absolute timeout rejected; later valid prompt succeeds'),
    ('list', ['CONSTANT-PROMPT-TYPE-LIST', 'EXAMPLE-115'], list_prompt, 'LRM p.71: keyed list returns selected key, first/last options; empty list fails before IPC; later valid list succeeds'),
    ('list-alpha', ['SYNTAX-PROMPT-LIST-ALPHA', 'EXAMPLE-117'], lambda d: list_prompt(d, alpha=True), 'LRM p.71: LIST|ALPHA returns selected value, first/last options; empty list fails; later valid list succeeds'),
    ('list-num', ['SYNTAX-PROMPT-LIST-NUM', 'EXAMPLE-116'], lambda d: list_prompt(d, numeric=True), 'LRM p.71 Example116: LIST|NUM returns zero-based option index; original source may conflict and must remain open if it returns one-based values'),
):
    for dimension in ('positive', 'boundary', 'failure', 'recovery'):
        check('prompt-' + name, contracts, dimension, lambda d=dimension: operation(d), oracle)

Path('ui-complete.json').write_text(json.dumps({'completed': True}), encoding='utf-8')
