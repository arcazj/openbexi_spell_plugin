"""Original native DataContainer/Var contracts through actual executor and CIF."""
import json
import os
import datetime
from pathlib import Path

from spell.lib.adapter.data import DataContainer, Var
from spell.lib.adapter.utctime import TIME
from spell.lib.exception import SyntaxException, DriverException
from spell.lang.constants import LONG, FLOAT, BOOLEAN, STRING, DATETIME, RELTIME, HEX, BIN, OCT, DEC

PREFIX = 'CMP-LRM244-'
checks = {}
active = {}


def equal(actual, expected):
    assert actual == expected and type(actual) is type(expected), (actual, expected, type(actual), type(expected))


def rejects(operation):
    try:
        operation()
    except (SyntaxException, DriverException, RuntimeError, TypeError, ValueError) as error:
        active['rejections'].append(type(error).__name__ + ': ' + str(error))
        return
    raise AssertionError('Invalid declaration or operation was accepted')


def persist():
    Path('dta-active.json').write_text(json.dumps(active), encoding='utf-8')


def answers(*rows):
    for contains, choices, answer in rows:
        active['prompts'].append(dict(contains=contains, choices=choices, answer=answer))
    persist()


def item(name, value, status='SUCCESS'):
    wanted = dict(ItemName=name, ItemStatus=status)
    if isinstance(value, TIME):
        actual = value.value()
        if isinstance(actual, datetime.datetime):
            wanted['time'] = dict(kind='absolute', value=actual.isoformat())
        else:
            wanted['time'] = dict(kind='relative', microseconds=(actual.days*86400+actual.seconds)*1000000+actual.microseconds)
    else:
        wanted['ItemValue'] = str(value)
    active['items'].append(wanted)


def container():
    return DataContainer('DTA:' + active['id'])


def key(suffix='value'):
    return 'DTA:' + active['id'] + ':' + suffix


def check(group, contracts, dimension, operation, oracle):
    global active
    selected = os.environ.get('DTA_GROUPS', '').split(',')
    if selected != [''] and group not in selected:
        return
    identifier = group + ':' + dimension
    active = dict(id=identifier, prompts=[], items=[], sequences={}, rejections=[])
    persist()
    row = dict(contracts=[PREFIX + value for value in contracts], dimension=dimension,
               passed=False, oracle=oracle)
    try:
        operation(dimension)
        row['passed'] = True
    except BaseException as error:
        row['error'] = type(error).__name__ + ': ' + str(error)
    row['expected'] = active
    checks[identifier] = row
    Path('dta-results.json').write_text(json.dumps(dict(schema='openbexi.spell.evidence/1', checks=checks), indent=2), encoding='utf-8')


TYPES = [
    ('LONG', LONG, 42, 0, 2**63-1, 'bad', '7', 7, []),
    ('FLOAT', FLOAT, 1.25, 0.0, -1.5, 'bad', '1E3', 1000.0, []),
    ('BOOLEAN', BOOLEAN, True, False, True, 1, '1', False, ['True', 'False']),
    ('STRING', STRING, 'text', '', 'café λ', 42, "O'Brien", "O'Brien", []),
    ('DATETIME', DATETIME, TIME('03-Apr-2006 09:52:34'), TIME('01-Jan-1970 00:00:00'),
     TIME('29-Feb-2000 00:00:00'), TIME('+00:00:01'), '29-Feb-2000 00:00:00', TIME('29-Feb-2000 00:00:00'), []),
    ('RELTIME', RELTIME, TIME('+00:00:05'), TIME('+00:00:00'), TIME('-00:00:01'),
     TIME('01-Jan-2000 00:00:00'), '+00:00:07', TIME('+00:00:07'), []),
]


def typed(dimension, spec):
    name, code, initial, first, last, invalid, answer, corrected, choices = spec
    data, variable = container(), key()
    data[variable] = Var(Default=initial, Type=code)
    if dimension in ('positive', 'boundary'):
        for value in ([initial] if dimension == 'positive' else [first, last]):
            data[variable] = value
            equal(data[variable], value)
            item(variable, value)
        if name == 'FLOAT' and dimension == 'boundary':
            data[variable] = 2**40
            equal(data[variable], float(2**40))
        if name in ('RELTIME', 'DATETIME') and dimension == 'boundary':
            times = (['-00:00:00.000001', '-00:00:00.5', '-00:00:01.5', '+00:00:00.000001']
                     if name == 'RELTIME' else ['31-Dec-1969 23:59:59.5', '29-Feb-2000 00:00:00.123456'])
            for text in times:
                value = TIME(text)
                data[variable] = value
                equal(data[variable], value)
                item(variable, value)
    else:
        answers(('do not match', choices, answer))
        data[variable] = invalid
        equal(data[variable], corrected)
        item(variable, invalid, 'FAILED')
        item(variable, corrected)
        if dimension == 'recovery':
            data[variable] = initial
            equal(data[variable], initial)


for spec in TYPES:
    for dimension in ('positive', 'boundary', 'failure', 'recovery'):
        check('typed-' + spec[0].lower(), ['TYPE-DATA-CONTAINER-' + spec[0]], dimension,
              lambda dimension, spec=spec: typed(dimension, spec),
              'LRM pp.84-85: native typed assignment/read and ITEM notifications; exact type/zero/empty/time boundaries; invalid assignment emits FAILED and requests real client correction, then same container remains usable')


def mapping(dimension):
    data = container()
    if dimension in ('failure', 'recovery'):
        for operation in (lambda: data.__setitem__([], 1), lambda: data.get(), lambda: data.set('short'),
                          lambda: DataContainer('one', 'two')):
            rejects(operation)
    if dimension != 'failure':
        equal(len(data), 0)
        values = [('first', 1), ('second', 2)] if dimension == 'positive' else [(1, 0), (2.5, -2), ('λ', 3)]
        for name, value in values:
            data.set(name, value)
        equal(data.keys(), [name for name, value in values])
        equal(list(data), [name for name, value in values])
        equal(len(data), len(values))
        for name, value in values:
            equal(data.has_key(name), True)
            equal(data.get(name), value)
        equal(data.has_key('missing'), False)


def declarations(dimension):
    data, variable = container(), key()
    if dimension in ('failure', 'recovery'):
        for modifiers in (dict(Type='UNKNOWN'), dict(Confirm='yes'), dict(Default='x', Type=LONG),
                          dict(Default=1, Range=[0, 10], Expected=[1, 2]),
                          dict(Default='b', Range=['a', 'z']), dict(Range=[10, 0]),
                          dict(Range=[0]), dict(Expected=[]), dict(ValueFormat='UNKNOWN', Type=LONG)):
            rejects(lambda modifiers=modifiers: Var(**modifiers))
    if dimension != 'failure':
        data[variable] = Var(Default=5, Type=LONG, Range=[0, 10])
        for value in (5,) if dimension == 'positive' else (0, 10):
            data[variable] = value
            equal(data[variable], value)
        data[key('expected')] = Var(Default='A', Expected=['A', 'B'])
        data[key('expected')] = 'B'
        equal(data[key('expected')], 'B')


def constraints(dimension):
    data, variable = container(), key()
    data[variable] = Var(Range=[0, 10])
    if dimension == 'positive':
        data[variable] = 5
        equal(data[variable], 5)
    elif dimension == 'boundary':
        for value in (0, 10):
            data[variable] = value
            equal(data[variable], value)
    else:
        answers(('below range', [], '11'), ('above range', [], '7'))
        data[variable] = -1
        equal(data[variable], 7)
        item(variable, '-1', 'FAILED')
        item(variable, '11', 'FAILED')
        if dimension == 'recovery':
            data[variable] = 3
            equal(data[variable], 3)
    selected = key('selected')
    data[selected] = Var(Expected=['A', 'B'])
    if dimension in ('failure', 'recovery'):
        answers(('not in the list', ["'A'", "'B'"], '1'))
        data[selected] = 'C'
        equal(data[selected], 'B')
    else:
        data[selected] = 'A' if dimension == 'positive' else 'B'
        equal(data[selected], 'A' if dimension == 'positive' else 'B')


def initialization(dimension):
    data, variable = container(), key()
    data[variable] = Var()
    answer = "'fresh'" if dimension == 'boundary' else '42'
    expected = 'fresh' if dimension == 'boundary' else 42
    if dimension in ('failure', 'recovery'):
        answers(('not initialized', [], 'not_a_python_literal'), ('', [], '42'))
    else:
        answers(('not initialized', [], answer))
    equal(data[variable], expected)
    equal(data[variable], expected)  # inferred value is retained, without another prompt
    missing = key('missing')
    answers(('does not contain variable', [], '7'))
    equal(data[missing], 7)
    equal(data.has_key(missing), True)
    assert missing in data.keys()
    if dimension == 'recovery':
        data[variable] = 9
        equal(data[variable], 9)


def confirmation(dimension):
    data, variable = container(), key()
    if dimension == 'failure':
        rejects(lambda: Var(Confirm=1))
        return
    data[variable] = Var(Default=5, Type=LONG, Confirm=True)
    if dimension == 'positive':
        answers(('Is it correct', ['1', '2'], '0'), ('Is it correct', ['1', '2'], '0'))
        equal(data[variable], 5)
        equal(data[variable], 5)
    else:
        answers(('Is it correct', ['1', '2'], '1'), ('Please provide a new value', [], '0'),
                ('Is it correct', ['1', '2'], '0'))
        equal(data[variable], 0)
        equal(data[variable], 0)


def formats(dimension):
    data = container()
    if dimension in ('failure', 'recovery'):
        rejects(lambda: Var(Default='x', ValueFormat=HEX))
    if dimension == 'failure':
        return
    for number in ([0, 2**40+31, -(2**40+31)] if dimension == 'boundary' else [31]):
        sign, magnitude = ('-' if number < 0 else ''), abs(number)
        for code, expected in ((DEC, str(number)), (HEX, sign+'0x'+format(magnitude, 'X')),
                               (BIN, bin(number)), (OCT, sign+'0'+format(magnitude, 'o'))):
            variable = key(code + ':' + str(number))
            data[variable] = Var(Default=number, Type=LONG, ValueFormat=code)
            equal(data[variable], number)
            item(variable, expected)


def deferred_format(dimension):
    data, variable = container(), key()
    data[variable] = Var(ValueFormat=HEX)
    if dimension in ('failure', 'recovery'):
        answers(('requires a LONG', [], '1.5'), ('requires a LONG', [], '31'))
        data[variable] = 'bad'
        equal(data[variable], 31)
    else:
        data[variable] = 0 if dimension == 'boundary' else 31
        equal(data[variable], 0 if dimension == 'boundary' else 31)
    if dimension == 'recovery':
        data[variable] = 255
        equal(data[variable], 255)
        item(variable, '0xFF')


def literal_inputs(dimension):
    data, variable = container(), key()
    data[variable] = Var(Type=LONG)
    if dimension in ('failure', 'recovery'):
        answers(('not initialized', [], '40 + 2'), ('', [], '42'))
    else:
        answers(('not initialized', [], '0x2a' if dimension == 'boundary' else '42'))
    equal(data[variable], 42)
    quoted = key('quoted')
    data[quoted] = Var(Type=STRING)
    if dimension in ('failure', 'recovery'):
        answers(('not initialized', [], "'wrong' if False else 'executed'"), ('', [], 'literal text'))
        equal(data[quoted], 'literal text')
    else:
        answers(('not initialized', [], '"quoted"' if dimension == 'positive' else 'a:b'))
        equal(data[quoted], 'quoted' if dimension == 'positive' else 'a:b')
    expected = key('expected')
    data[expected] = Var(Expected=["O'Brien", 'a:b'])
    answers(('not initialized', ["'O\'Brien'", "'a:b'"], '0' if dimension == 'positive' else '1'))
    equal(data[expected], "O'Brien" if dimension == 'positive' else 'a:b')


def notifications(dimension):
    data, variable = container(), key('λ' if dimension == 'boundary' else 'value')
    data[variable] = Var(Default=3, Type=LONG)
    expected = []
    def read(value):
        equal(data[variable], value)
        expected.extend([['IN PROGRESS', '...'], ['SUCCESS', str(value)]])
    read(3)
    if dimension in ('failure', 'recovery'):
        answers(('do not match', [], '7'))
        data[variable] = 'bad'
        expected.extend([['IN PROGRESS', 'bad'], ['FAILED', 'bad'], ['IN PROGRESS', '7'], ['SUCCESS', '7']])
        read(7)
    if dimension != 'failure':
        data[variable] = 0 if dimension == 'boundary' else 4
        expected.extend([['IN PROGRESS', str(0 if dimension == 'boundary' else 4)],
                         ['SUCCESS', str(0 if dimension == 'boundary' else 4)]])
        read(0 if dimension == 'boundary' else 4)
    active['sequences'][variable] = expected


def time_constraints(dimension):
    data, variable = container(), key()
    data[variable] = Var(Type=RELTIME, Range=[TIME('-00:00:01.5'), TIME('+00:00:01.5')])
    if dimension in ('failure', 'recovery'):
        answers(('below range', [], '+00:00:00.5'))
        data[variable] = TIME('-00:00:02')
        equal(data[variable], TIME('+00:00:00.5'))
    if dimension != 'failure':
        for text in ('-00:00:01.5', '+00:00:01.5', '-00:00:00.5'):
            data[variable] = TIME(text)
            equal(data[variable], TIME(text))
    expected = key('expected')
    data[expected] = Var(Type=DATETIME, Expected=[TIME('01-Jan-1970 00:00:00'), TIME('29-Feb-2000 00:00:00')])
    answers(('not initialized', ['1970-01-01 00:00:00', '2000-02-29 00:00:00'], '0' if dimension == 'boundary' else '1'))
    equal(data[expected], TIME('01-Jan-1970 00:00:00') if dimension == 'boundary' else TIME('29-Feb-2000 00:00:00'))


for group, contracts, operation, oracle in (
    ('mapping', ['TYPE-DATACONTAINER', 'EXAMPLE-149'], mapping, 'LRM p.85: native mapping keys/order/iteration and methods; empty/numeric/Unicode boundaries; invalid calls reject without corruption'),
    ('declarations', ['SYNTAX-DATA-CONTAINER-VAR', 'EXAMPLE-150'], declarations, 'LRM pp.84-85: explicit/inferred native variable declarations and independent modifier consistency checks; invalid definitions reject before storage'),
    ('constraints', ['MODIFIER-RANGE'], constraints, 'LRM pp.84-85: inclusive limits, inferred type and expected choices; failed assignments remain in real prompt loop until an allowed value is supplied'),
    ('initialization', ['CONSTANT-PYTHON-SENTINEL-NONE'], initialization, 'LRM pp.84-85: None is uninitialized and cannot be consumed; unset/missing variables prompt for value, infer type and remain registered after correction'),
    ('confirmation', [], confirmation, 'LRM p.85: Confirm=True asks before each use, accepts or replaces value through actual native CIF; invalid Confirm fails'),
    ('formats', [], formats, 'LRM p.85: LONG HEX/BIN/OCT/DEC affect actual ITEM display, not numeric stored value; large integers must retain all digits and invalid type/format fails'),
    ('deferred-format', [], deferred_format, 'LRM p.85: ValueFormat declared before type inference still restricts values to LONG; invalid first values stay unset through repeated native correction prompts and a valid integer permits later updates'),
    ('literal-inputs', [], literal_inputs, 'LRM pp.84-85 typed user inputs: literal data is accepted, expression-shaped answers are never executed; invalid input reprompts and a later literal recovers; selected Expected strings preserve apostrophes and colons'),
    ('notifications', [], notifications, 'LRM p.84: every native read/assignment has exact IN PROGRESS then SUCCESS/FAILED ITEM messages and values; failed assignment prompts and corrected read/write operations recover in the same container'),
    ('time-constraints', [], time_constraints, 'LRM pp.84-85: native RELTIME limits use chronological order across zero and signed fractions; DATETIME Expected values round-trip at epoch zero and leap day; rejected range assignment recovers through actual prompt'),
):
    for dimension in ('positive', 'boundary', 'failure', 'recovery'):
        check(group, contracts, dimension, operation, oracle)

Path('dta-complete.json').write_text(json.dumps({'complete': True}), encoding='utf-8')
