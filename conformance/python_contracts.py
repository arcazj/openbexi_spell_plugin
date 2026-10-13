"""Independent LRM Python oracles, run in the original native SPELL executor.

No interpreter, built-in, language helper, registry or driver is replaced.
Imported oracle functions do not claim checkpoint or native line-control support.
"""
import json
import math
from pathlib import Path
import platform
import sys
import textwrap

import spell.lib
from spell.lib.registry import REGISTRY

PREFIX = 'CMP-LRM244-'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
cases, sections = {}, {}
LEGACY = {'METHOD-DICTIONARY-HAS-KEY', 'OPERATOR-PYTHON-LEGACY-NOT-EQUAL',
          'SYNTAX-INTEGER-OCTAL'}


def equal(actual, expected):
    if type(expected) is float:
        assert type(actual) in (float, int), (type(actual), actual)
        assert math.isclose(actual, expected, rel_tol=1e-13, abs_tol=1e-13), (actual, expected)
    else:
        assert actual == expected, (actual, expected)
    return


def rejects(error, operation):
    try:
        operation()
    except error:
        return
    raise AssertionError('Expected ' + error.__name__ + '; operation returned normally')


def case(suffix, positive, boundary, failure, recovery=None):
    assert PREFIX + suffix not in cases, suffix
    sources = dict(positive=positive, boundary=boundary, failure=failure)
    sources['recovery'] = recovery if recovery is not None else (
        textwrap.dedent(failure) + '\n' + textwrap.dedent(positive))
    cases[PREFIX + suffix] = {
        'sources': {key: textwrap.dedent(value).strip() + '\n' for key, value in sources.items()},
        'oracle': 'LRM 2.4.4 Python chapter; literal expected values and specific exception types; explicit CPython 3.13/manual decisions in conformance/python.md',
        'legacy_spelling_supported': False if suffix in LEGACY else None,
    }
    return


def same_case(suffix, original):
    # A syntax row repeats the specific example's executable assertions, with
    # its own result and source, rather than passing on inventory membership.
    source = cases[PREFIX + original]['sources']
    case(suffix, **source)
    return


def section(suffix, members):
    sections[PREFIX + suffix] = [PREFIX + member for member in members]
    return


case('EXAMPLE-001', '''
    A = 1
    if A == 1:
        B = 2
    else:
        B = 4
    C = 4
    assert (B, C) == (2, 4)
''', '''
    A = 0
    if A == 1:
        B = 2
    else:
        B = 4
    C = 4
    assert (B, C) == (4, 4)
''', "rejects(IndentationError, lambda: compile('if True:\\nx = 1\\n', '<bad-indent>', 'exec'))")
case('EXAMPLE-002', '''
    A = 'This is a very long string and I have to split it in several lines so that it is not too long'
    if (A == 'This is a very long string and ' +
             'I have to split it in several ' +
             'lines so that it is not too long'):
        result = True
    else:
        result = False
    assert result is True
''', "assert ('' +\n        'tail') == 'tail'", "rejects(TypeError, lambda: 'text' + 3)")
case('EXAMPLE-003', '''
    def Long_Function_Call(argument1, argument2, argument3):
        return [argument1, argument2, argument3]
    result = Long_Function_Call(argument1=1,
                                argument2=2,
                                argument3=3)
    my_list = [43545,
               21234,
               32443]
    my_dict = {1: 'Parameter A',
               2: 'Parameter B',
               3: 'Parameter C'}
    assert result == [1, 2, 3]
    assert my_list == [43545, 21234, 32443]
    assert my_dict[3] == 'Parameter C'
''', "assert [1,\n       ] == [1]\nassert {'a': 1,\n       } == {'a': 1}",
     "rejects(SyntaxError, lambda: compile('x = [1\\n2]', '<missing-comma>', 'exec'))")
case('EXAMPLE-004', "A = 45\nX = 1 + 45 -\\\n    23+5.4 + A/45\nequal(X, 29.4)\nA, B, C = True, False, False\ncondition = A and B \\\n                    or not C\nassert condition is True",
     "x = 0 +\\\n    0\nassert x == 0",
     "rejects(SyntaxError, lambda: compile('x = 1 +\\\\ \\n2', '<trailing-space>', 'exec'))")
case('EXAMPLE-005', "# This is a comment line\nA = 1 # This is an in-line comment\nassert A == 1",
     "A = '# retained' # comment\nassert A == '# retained'",
     "rejects(NameError, lambda: eval('missing_name # assignment never ran'))")
case('EXAMPLE-006', "'''This is a multi-line comment\nThis is a multi-line comment'''\nA = 4\nassert A == 4",
     '"""module documentation"""\nassert __doc__ == "module documentation"',
     'rejects(SyntaxError, lambda: compile("\'\'\'unterminated", "<bad-string>", "exec"))')
case('EXAMPLE-007', '''
    A = 1
    assert type(A) is int
    A = 'This is a string'
    assert type(A) is str
    A = ['1', 1.0, {'KEY': 'VALUE'}]
    assert type(A) is list and A[2]['KEY'] == 'VALUE'
''', "A = None\nA = []\nassert A == [] and type(A) is list",
     "rejects(NameError, lambda: not_yet_assigned)")
case('EXAMPLE-008', '''
    mylist = [111, 222, 333, 444]
    mydict = {1: 'FOO', 2: 'BAR'}
    biglist = [[1, 2, 3, 4], 'My string', {'A': 'Option 1'}]
    assert mylist[2] == 333 and mydict[2] == 'BAR'
    assert biglist[0][3] == 4 and biglist[2]['A'] == 'Option 1'
''', "assert [111][-1] == 111\nassert {} == {}\nassert [] == []",
     "rejects(IndexError, lambda: [111][1])\nrejects(KeyError, lambda: {1: 'FOO'}[2])")
case('EXAMPLE-009', '''
    a = abs(-7.5)
    b = math.asin(0.5)
    c = pow(b, 3)
    d = ((max(a, b) + 2.0) % 10) * a
    equal(a, 7.5)
    equal(b, 0.5235987755982989)
    equal(c, 0.14354757722361028)
    equal(d, 71.25)
''', "assert abs(0) == 0 and pow(7, 0) == 1 and 10 % 10 == 0",
     "rejects(ValueError, lambda: math.asin(2))\nrejects(ZeroDivisionError, lambda: 7 % 0)")
case('EXAMPLE-010', "a, b, c = 1, 2, 3\nassert ((a != b) and (not (b > c))) is True\nassert (True or (b == c)) is True",
     "assert (False and (1 / 0)) is False\nassert (True or (1 / 0)) is True",
     "rejects(TypeError, lambda: 2 > '3')")
case('EXAMPLE-011', "i = 5\nmyvar = 'Integer:' + str(i) + ', Binary: ' + bin(i)\nassert myvar == 'Integer:5, Binary: 0b101'",
     "assert 'Integer:' + str(0) + ', Binary: ' + bin(0) == 'Integer:0, Binary: 0b0'",
     "rejects(TypeError, lambda: 'Integer:' + 5)")
case('EXAMPLE-012', "A = 'This is a string'\nassert A[0] == 'T' and A[-1] == 'g'\nassert A[0:3] == 'Thi' and A[:3] == 'Thi'\nassert A[0:4] == 'This' and A[4:] == ' is a string'",
     "assert ''[:] == '' and 'abc'[3:3] == '' and 'abc'[-100:100] == 'abc'",
     "rejects(IndexError, lambda: ''[0])\nrejects(ValueError, lambda: 'abc'[::0])")
case('EXAMPLE-013', '''
    results = []
    for value in (1, 0, -1):
        if value > 0:
            results.append('positive')
        elif value == 0:
            results.append('zero')
        else:
            results.append('negative')
    assert results == ['positive', 'zero', 'negative']
''', "if []:\n    result = 1\nelse:\n    result = 0\nassert result == 0",
     "rejects(SyntaxError, lambda: compile('if True\\n    pass', '<missing-colon>', 'exec'))")
case('EXAMPLE-014', '''
    visited = []
    for count in [1, 2, 3, 4, 5]:
        visited.append(count)
    assert visited == [1, 2, 3, 4, 5]
    visited = []
    for key in {'A': 1, 'B': 2, 'C': 2}:
        visited.append(key)
    assert visited == ['A', 'B', 'C']
    total = 0
    for count in range(0, 100):
        total += count
    assert total == 4950 and count == 99
    visited = []
    for element in ['text', None, {'key': 1}]:
        visited.append(element)
    assert visited == ['text', None, {'key': 1}]
''', "visited = []\nfor value in []:\n    visited.append(value)\nassert visited == []",
     "rejects(TypeError, lambda: iter(3))")
case('EXAMPLE-015', "count = 3\nvisited = []\nwhile count > 0:\n    visited.append(count)\n    count -= 1\nassert visited == [3, 2, 1] and count == 0",
     "count = 0\nwhile False:\n    count += 1\nassert count == 0",
     "rejects(SyntaxError, lambda: compile('while True\\n    break', '<missing-colon>', 'exec'))")
case('EXAMPLE-016', '''
    def function(x, y):
        a, b, c = x + y, x - y, x * y
        return [a, b, c]
    x, y, z = function(1, 2)
    assert (x, y, z) == (3, -1, 2)
    assert 'a' not in globals() and 'b' not in globals() and 'c' not in globals()
''', "def function(x, y):\n    return [x + y, x - y, x * y]\nassert function(0, 0) == [0, 0, 0]",
     "def function(x, y):\n    return [x + y, x - y, x * y]\nrejects(TypeError, lambda: function(1))")
case('EXAMPLE-017', '''
    def functionA(x):
        x = x + 1
        return
    def functionB(lst):
        lst[0] = 99
        return
    x = 1
    assert functionA(x) is None and x == 1
    x = [1, 2, 3]
    assert functionB(x) is None and x == [99, 2, 3]
''', "def modify(mapping):\n    mapping['key'] = 2\n    return\nx = {}\nmodify(x)\nassert x == {'key': 2}",
     "def modify(x):\n    x[0] = 99\n    return\nrejects(TypeError, lambda: modify((1, 2)))")
case('EXAMPLE-018', "import python_fixture\nassert python_fixture.combine(1, 2) == [3, -1, 2]",
     "import python_fixture\nold = python_fixture.identity\nimport python_fixture as again\nassert again is python_fixture and again.identity is old",
     "rejects(ModuleNotFoundError, lambda: __import__('python_contract_missing_module'))")

for name, positive, boundary, failure in (
    ('BIN', "assert bin(5) == '0b101'", "assert bin(0) == '0b0' and bin(-5) == '-0b101'", "rejects(TypeError, lambda: bin(1.5))"),
    ('HEX', "assert hex(255) == '0xff'", "assert hex(0) == '0x0' and hex(-16) == '-0x10'", "rejects(TypeError, lambda: hex('255'))"),
    ('OCT', "assert oct(29) == '0o35'", "assert oct(0) == '0o0' and oct(-8) == '-0o10'", "rejects(TypeError, lambda: oct(8.0))"),
    ('RANGE', "assert list(range(2, 9, 2)) == [2, 4, 6, 8]", "assert list(range(0)) == []\nassert list(range(3, -1, -1)) == [3, 2, 1, 0]", "rejects(ValueError, lambda: range(1, 4, 0))\nrejects(TypeError, lambda: range(1.5))"),
    ('REPR', "assert repr('line\\n') == \"'line\\\\n'\"\nassert repr([1, 'a']) == \"[1, 'a']\"", "assert repr('') == \"''\" and repr(None) == 'None'", "class Bad:\n    def __repr__(self):\n        return 7\nrejects(TypeError, lambda: repr(Bad()))"),
    ('STR', "assert str(42) == '42' and str(True) == 'True'", "assert str('') == '' and str(None) == 'None'", "class Bad:\n    def __str__(self):\n        return 7\nrejects(TypeError, lambda: str(Bad()))"),
):
    case('METHOD-CONVERSION-' + name, positive, boundary, failure)
case('METHOD-DICTIONARY-HAS-KEY',
     "mapping = {'x': 1}\nassert ('x' in mapping) is True and ('y' in mapping) is False",
     "assert ('' in {'': None}) is True\nassert ('x' in {}) is False",
     "rejects(AttributeError, lambda: {}.has_key('x'))\nrejects(TypeError, lambda: [] in {})")
case('METHOD-DICTIONARY-KEYS',
     "mapping = {'first': 1, 'second': 2}\nassert list(mapping.keys()) == ['first', 'second']",
     "mapping = {}\nview = mapping.keys()\nassert list(view) == []\nmapping['added'] = 3\nassert list(view) == ['added']",
     "rejects(TypeError, lambda: {}.keys(1))\nrejects(TypeError, lambda: {'a': 1}.keys()[0])")

# Mathematical expectations are literals, not calculated by the method tested.
for name, positive, boundary, failure in (
    ('ABS', "equal(abs(-7.5), 7.5)", "assert abs(0) == 0 and abs(-(2**200)) == 2**200", "rejects(TypeError, lambda: abs('7'))"),
    ('ACOS', "equal(math.acos(0.5), 1.0471975511965979)", "equal(math.acos(1), 0.0)\nequal(math.acos(-1), 3.141592653589793)", "rejects(ValueError, lambda: math.acos(1.01))"),
    ('ASIN', "equal(math.asin(0.5), 0.5235987755982989)", "equal(math.asin(1), 1.5707963267948966)\nequal(math.asin(-1), -1.5707963267948966)", "rejects(ValueError, lambda: math.asin(-1.01))"),
    ('ATAN', "equal(math.atan(1), 0.7853981633974483)", "equal(math.atan(0), 0.0)\nequal(math.atan(float('inf')), 1.5707963267948966)", "rejects(TypeError, lambda: math.atan('1'))"),
    ('CEIL', "assert math.ceil(2.1) == 3 and math.ceil(-2.1) == -2", "assert math.ceil(0) == 0 and math.ceil(3.0) == 3", "rejects(ValueError, lambda: math.ceil(float('nan')))\nrejects(OverflowError, lambda: math.ceil(float('inf')))"),
    ('COS', "equal(math.cos(1.0471975511965979), 0.5)", "equal(math.cos(0), 1.0)\nequal(math.cos(3.141592653589793), -1.0)", "rejects(ValueError, lambda: math.cos(float('inf')))"),
    ('DEGREES', "equal(math.degrees(1.5707963267948966), 90.0)", "equal(math.degrees(0), 0.0)\nequal(math.degrees(-3.141592653589793), -180.0)", "rejects(TypeError, lambda: math.degrees(None))"),
    ('EXP', "equal(math.exp(1), 2.718281828459045)", "equal(math.exp(0), 1.0)\nassert math.exp(float('-inf')) == 0", "rejects(OverflowError, lambda: math.exp(1000))"),
    ('FLOOR', "assert math.floor(2.9) == 2 and math.floor(-2.1) == -3", "assert math.floor(0) == 0 and math.floor(3.0) == 3", "rejects(ValueError, lambda: math.floor(float('nan')))\nrejects(OverflowError, lambda: math.floor(float('inf')))"),
    ('LOG', "equal(math.log(2.718281828459045), 1.0)\nequal(math.log(8, 2), 3.0)", "equal(math.log(1), 0.0)\nequal(math.log(0.5, 2), -1.0)", "rejects(ValueError, lambda: math.log(0))\nrejects(ValueError, lambda: math.log(-1))\nrejects(ZeroDivisionError, lambda: math.log(8, 1))"),
    ('LOG10', "equal(math.log10(1000), 3.0)", "equal(math.log10(1), 0.0)\nequal(math.log10(0.1), -1.0)", "rejects(ValueError, lambda: math.log10(0))"),
    ('MAX', "assert max(4, -8, 12, 0) == 12", "assert max([-3]) == -3 and max([], default=7) == 7", "rejects(ValueError, lambda: max([]))\nrejects(TypeError, lambda: max(1, '2'))"),
    ('MIN', "assert min(4, -8, 12, 0) == -8", "assert min([3]) == 3 and min([], default=7) == 7", "rejects(ValueError, lambda: min([]))\nrejects(TypeError, lambda: min(1, '2'))"),
    ('POW', "assert pow(2, 10) == 1024 and pow(2, 5, 7) == 4", "assert pow(0, 0) == 1\nequal(pow(2, -3), 0.125)", "rejects(ZeroDivisionError, lambda: pow(0, -1))"),
    ('RADIANS', "equal(math.radians(90), 1.5707963267948966)", "equal(math.radians(0), 0.0)\nequal(math.radians(-180), -3.141592653589793)", "rejects(TypeError, lambda: math.radians('90'))"),
    ('ROUND', "equal(round(1.23456, 3), 1.235)", "assert round(2.5) == 2 and round(3.5) == 4\nassert round(125, -1) == 120", "rejects(TypeError, lambda: round(1.2, 1.5))\nrejects(ValueError, lambda: round(float('nan')))"),
    ('SIN', "equal(math.sin(0.5235987755982989), 0.5)", "equal(math.sin(0), 0.0)\nequal(math.sin(-1.5707963267948966), -1.0)", "rejects(ValueError, lambda: math.sin(float('inf')))"),
    ('SQRT', "equal(math.sqrt(144), 12.0)", "equal(math.sqrt(0), 0.0)\nequal(math.sqrt(0.25), 0.5)", "rejects(ValueError, lambda: math.sqrt(-1))"),
    ('TAN', "equal(math.tan(0.7853981633974483), 1.0)", "equal(math.tan(0), 0.0)\nequal(math.tan(-0.7853981633974483), -1.0)", "rejects(ValueError, lambda: math.tan(float('inf')))"),
):
    case('METHOD-MATH-' + name, positive, boundary, failure)

# All thirteen documented string operations, including Unicode and empty input.
for name, positive, boundary, failure in (
    ('CAPITALIZE', "assert 'hELLO'.capitalize() == 'Hello' and 'éCOLE'.capitalize() == 'École'", "assert ''.capitalize() == '' and '7ABC'.capitalize() == '7abc'", "rejects(TypeError, lambda: 'a'.capitalize(1))"),
    ('CENTER', "assert 'abc'.center(7, '-') == '--abc--'", "assert 'abc'.center(1) == 'abc' and ''.center(2) == '  '", "rejects(TypeError, lambda: 'a'.center(5, 'xx'))\nrejects(TypeError, lambda: 'a'.center(2.5))"),
    ('ENDSWITH', "assert 'telemetry.dat'.endswith('.dat') is True\nassert 'telemetry.dat'.endswith('.txt') is False", "assert ''.endswith('') is True and 'abc'.endswith('b', 0, 2) is True", "rejects(TypeError, lambda: 'abc'.endswith(1))"),
    ('FIND', "assert 'banana'.find('na') == 2 and 'banana'.find('na', 3, 6) == 4", "assert ''.find('') == 0 and 'abc'.find('z') == -1 and 'banana'.find('na', 0, 3) == -1", "rejects(TypeError, lambda: 'abc'.find(1))"),
    ('ISALPHA', "assert 'Abcé'.isalpha() is True and 'abc3'.isalpha() is False", "assert ''.isalpha() is False and ' '.isalpha() is False", "rejects(TypeError, lambda: 'a'.isalpha(1))"),
    ('ISDIGIT', "assert '0123456789'.isdigit() is True and '²'.isdigit() is True\nassert '12.3'.isdigit() is False", "assert ''.isdigit() is False and '-1'.isdigit() is False", "rejects(TypeError, lambda: '1'.isdigit(1))"),
    ('ISLOWER', "assert 'abc 123'.islower() is True and 'abC'.islower() is False", "assert ''.islower() is False and '123'.islower() is False", "rejects(TypeError, lambda: 'a'.islower(1))"),
    ('ISSPACE', "assert ' \\t\\r\\n'.isspace() is True and ' a'.isspace() is False", "assert ''.isspace() is False and '\\u2003'.isspace() is True", "rejects(TypeError, lambda: ' '.isspace(1))"),
    ('ISUPPER', "assert 'ABC 123'.isupper() is True and 'ABc'.isupper() is False", "assert ''.isupper() is False and '123'.isupper() is False", "rejects(TypeError, lambda: 'A'.isupper(1))"),
    ('LOWER', "assert 'HELLO É'.lower() == 'hello é'", "assert ''.lower() == '' and '123'.lower() == '123'", "rejects(TypeError, lambda: 'A'.lower(1))"),
    ('REPLACE', "original = 'a-b-a'\nassert original.replace('a', 'xy') == 'xy-b-xy' and original == 'a-b-a'", "assert 'aaa'.replace('a', 'b', 0) == 'aaa'\nassert 'aaa'.replace('a', 'b', 1) == 'baa' and ''.replace('', '-') == '-'", "rejects(TypeError, lambda: 'a'.replace('a', 3))"),
    ('STARTSWITH', "assert 'telemetry.dat'.startswith('tele') is True\nassert 'telemetry.dat'.startswith('data') is False", "assert ''.startswith('') is True and 'abc'.startswith('b', 1, 2) is True", "rejects(TypeError, lambda: 'abc'.startswith(1))"),
    ('UPPER', "assert 'hello é'.upper() == 'HELLO É' and 'straße'.upper() == 'STRASSE'", "assert ''.upper() == '' and '123'.upper() == '123'", "rejects(TypeError, lambda: 'a'.upper(1))"),
):
    case('METHOD-STRING-' + name, positive, boundary, failure)

for name, positive, boundary, failure in (
    ('ADD', "assert 7 + 5 == 12\nequal(1.25 + 2.5, 3.75)", "assert 0 + 0 == 0 and (2**200) + 1 > 2**200", "rejects(TypeError, lambda: 1 + '2')"),
    ('AND', "assert (True and False) is False and (True and True) is True", "assert (0 and (1 / 0)) == 0 and ('left' and 'right') == 'right'", "class Bad:\n    def __bool__(self):\n        raise ValueError('invalid truth')\nrejects(ValueError, lambda: Bad() and True)"),
    ('BITWISE-AND', "assert (0b1010 & 0b1100) == 8", "assert (0 & 255) == 0 and (-1 & 255) == 255", "rejects(TypeError, lambda: 1.5 & 1)"),
    ('BITWISE-OR', "assert (0b1010 | 0b1100) == 14", "assert (0 | 255) == 255 and (-1 | 255) == -1", "rejects(TypeError, lambda: 1.5 | 1)"),
    ('DIVIDE', "equal(7 / 2, 3.5)\nassert type(4 / 2) is float", "equal(0 / 3, 0.0)\nequal(-7 / 2, -3.5)", "rejects(ZeroDivisionError, lambda: 7 / 0)"),
    ('EQUAL', "assert (2 == 2) is True and (2 == 3) is False", "assert (1 == 1.0) is True and (0 == False) is True and ([] == []) is True", "class Bad:\n    def __eq__(self, other):\n        raise ValueError('invalid comparison')\nrejects(ValueError, lambda: Bad() == 1)"),
    ('GREATER', "assert (3 > 2) is True and (2 > 3) is False", "assert (2 > 2) is False and (-1 > -2) is True", "rejects(TypeError, lambda: 2 > '2')"),
    ('GREATER-EQUAL', "assert (3 >= 2) is True and (2 >= 3) is False", "assert (2 >= 2) is True and (-2 >= -1) is False", "rejects(TypeError, lambda: 2 >= '2')"),
    ('LEGACY-NOT-EQUAL', "assert (1 != 2) is True", "assert (0 != False) is False and ([] != []) is False", "rejects(SyntaxError, lambda: compile('1 <> 2', '<legacy-not-equal>', 'eval'))"),
    ('LESS', "assert (2 < 3) is True and (3 < 2) is False", "assert (2 < 2) is False and (-2 < -1) is True", "rejects(TypeError, lambda: 2 < '2')"),
    ('LESS-EQUAL', "assert (2 <= 3) is True and (3 <= 2) is False", "assert (2 <= 2) is True and (-1 <= -2) is False", "rejects(TypeError, lambda: 2 <= '2')"),
    ('MODULUS', "assert 17 % 5 == 2 and -17 % 5 == 3", "assert 0 % 3 == 0 and 6 % 3 == 0 and 17 % -5 == -3", "rejects(ZeroDivisionError, lambda: 7 % 0)"),
    ('MULTIPLY', "assert 7 * 6 == 42\nequal(1.5 * 2, 3.0)", "assert 0 * 7 == 0 and -3 * -2 == 6", "rejects(TypeError, lambda: 2 * {})"),
    ('NOT', "assert (not True) is False and (not False) is True", "assert (not []) is True and (not [0]) is False", "class Bad:\n    def __bool__(self):\n        raise ValueError('invalid truth')\nrejects(ValueError, lambda: not Bad())"),
    ('NOT-EQUAL', "assert (2 != 3) is True and (2 != 2) is False", "assert (1 != 1.0) is False and ([] != [0]) is True", "class Bad:\n    def __ne__(self, other):\n        raise ValueError('invalid comparison')\nrejects(ValueError, lambda: Bad() != 1)"),
    ('OR', "assert (False or True) is True and (False or False) is False", "assert (1 or (1 / 0)) == 1 and ('' or 'fallback') == 'fallback'", "class Bad:\n    def __bool__(self):\n        raise ValueError('invalid truth')\nrejects(ValueError, lambda: Bad() or False)"),
    ('POWER', "assert 2 ** 10 == 1024 and (-2) ** 3 == -8", "assert 0 ** 0 == 1\nequal(2 ** -3, 0.125)", "rejects(ZeroDivisionError, lambda: 0 ** -1)"),
    ('SUBTRACT', "assert 9 - 4 == 5\nequal(2.5 - 1.25, 1.25)", "assert 0 - 0 == 0 and 0 - 7 == -7", "rejects(TypeError, lambda: 1 - '2')"),
):
    case('OPERATOR-PYTHON-' + name, positive, boundary, failure)
case('OPERATOR-STRING-CONCAT', "assert 'tele' + 'metry' == 'telemetry'",
     "assert '' + 'a' == 'a' and 'a' + '' == 'a'", "rejects(TypeError, lambda: 'a' + 1)")

for suffix, original in (
    ('INDENTED-BLOCK', '001'), ('MULTILINE-STRING-PLUS', '002'),
    ('MULTILINE-COMMA', '003'), ('MULTILINE-BACKSLASH', '004'),
    ('LINE-COMMENT', '005'), ('DOCSTRING-COMMENT', '006'),
    ('DYNAMIC-ASSIGNMENT', '007'), ('IF-ELIF-ELSE', '013'),
    ('FOR-IN', '014'), ('WHILE', '015'), ('FUNCTION-DEFINITION', '016'),
    ('IMPORT', '018'),
):
    same_case('SYNTAX-' + suffix, 'EXAMPLE-' + original)
case('SYNTAX-BREAK', "seen = []\nfor i in range(5):\n    if i == 2:\n        break\n    seen.append(i)\nelse:\n    seen.append('exhausted')\nassert seen == [0, 1]",
     "seen = []\nfor i in range(0):\n    break\nelse:\n    seen.append('empty')\nassert seen == ['empty']",
     "rejects(SyntaxError, lambda: compile('break', '<outside-loop>', 'exec'))")
case('SYNTAX-CASE-SENSITIVE-NAMES', "Value, value = 1, 2\nassert Value == 1 and value == 2",
     "A, a = None, False\nassert A is None and a is False", "Value = 1\nrejects(NameError, lambda: VALUE)")
case('SYNTAX-CONTINUE', "seen = []\nfor i in range(5):\n    if i % 2:\n        continue\n    seen.append(i)\nassert seen == [0, 2, 4]",
     "count = 0\nfor i in range(3):\n    count += 1\n    continue\n    count = -999\nassert count == 3",
     "rejects(SyntaxError, lambda: compile('continue', '<outside-loop>', 'exec'))")
case('SYNTAX-DICTIONARY-LITERAL', "mapping = {'a': 1, 2: 'b', (1, 2): [3]}\nassert mapping[(1, 2)] == [3] and mapping[2] == 'b'",
     "assert {} == {} and {'a': 1, 'a': 2} == {'a': 2}", "rejects(TypeError, lambda: {[]: 1})")
case('SYNTAX-DICTIONARY-LOOKUP', "assert {'key': 42}['key'] == 42",
     "assert {0: 'zero'}[False] == 'zero' and {'': None}[''] is None",
     "rejects(KeyError, lambda: {}['missing'])\nrejects(TypeError, lambda: {}[[]])")
case('SYNTAX-INDEX', "assert [10, 20, 30][1] == 20 and 'abc'[1] == 'b'",
     "assert [10][-1] == 10 and 'a'[-1] == 'a'",
     "rejects(IndexError, lambda: [10][1])\nrejects(IndexError, lambda: 'a'[-2])")
case('SYNTAX-INTEGER-BINARY', "assert 0b101001 == 41", "assert 0b0 == 0 and -0b1 == -1",
     "rejects(SyntaxError, lambda: compile('0b102', '<bad-binary>', 'eval'))")
case('SYNTAX-INTEGER-HEXADECIMAL', "assert 0xFF == 255", "assert 0x0 == 0 and -0xF == -15 and 0xff == 255",
     "rejects(SyntaxError, lambda: compile('0xFG', '<bad-hex>', 'eval'))")
case('SYNTAX-INTEGER-OCTAL', "assert 0o35 == 29", "assert 0o0 == 0 and -0o10 == -8",
     "rejects(SyntaxError, lambda: compile('035', '<legacy-octal>', 'eval'))\nrejects(SyntaxError, lambda: compile('0o8', '<bad-octal>', 'eval'))")
case('SYNTAX-LIST-LITERAL', "values = [1, 'two', [3], {'four': 4}]\nassert values[2][0] == 3 and values[3]['four'] == 4",
     "assert [] == [] and [None] == [None] and [1,] == [1]",
     "rejects(SyntaxError, lambda: compile('[1 2]', '<missing-comma>', 'eval'))")
case('SYNTAX-MULTIPLE-ASSIGNMENT', "x, y, z = [3, -1, 2]\nassert (x, y, z) == (3, -1, 2)",
     "(x,) = [0]\nassert x == 0\nx, y = 1, x\nassert (x, y) == (1, 0)",
     "namespace = {'x': 7, 'y': 8}\nrejects(ValueError, lambda: exec('x, y = [1]', namespace))\nassert (namespace['x'], namespace['y']) == (7, 8)")
case('SYNTAX-QUALIFIED-ACCESS', "import python_fixture\nassert python_fixture.combine(2, 2) == [4, 0, 4]",
     "import python_fixture\nassert callable(python_fixture.combine)\nassert python_fixture.identity is python_fixture.identity",
     "import python_fixture\nrejects(AttributeError, lambda: python_fixture.missing_entity)")
case('SYNTAX-SLICE', "assert 'abcdef'[1:4] == 'bcd' and [0, 1, 2, 3][1:3] == [1, 2]",
     "assert 'abc'[-100:100] == 'abc' and 'abc'[2:1] == '' and [1, 2, 3][::-1] == [3, 2, 1]",
     "rejects(ValueError, lambda: 'abc'[::0])\nrejects(TypeError, lambda: 'abc'[1.0:])")

case('TYPE-BOOLEAN', "assert type(True) is bool and type(False) is bool\nassert bool(1) is True and bool(0) is False",
     "assert bool([]) is False and bool([0]) is True and int(True) == 1",
     "rejects(SyntaxError, lambda: compile('True = 1', '<constant-assignment>', 'exec'))\nrejects(NameError, lambda: true)")
case('TYPE-DICTIONARY', "value = {'text': 1, 2: [3]}\nassert type(value) is dict and value[2] == [3]\nvalue['new'] = None\nassert value['new'] is None",
     "value = {}\nassert len(value) == 0\nvalue['x'] = 1\nvalue['x'] = 2\nassert value == {'x': 2}",
     "rejects(TypeError, lambda: {[]: 1})\nrejects(KeyError, lambda: {}['missing'])")
case('TYPE-FLOAT', "value = 1.23\nassert type(value) is float\nequal(value, 1.23)\nassert 7.8e-28 > 0",
     "assert math.copysign(1, -0.0) == -1\nassert float('inf') > 1e308 and math.isnan(float('nan'))",
     "rejects(ValueError, lambda: float('not-a-number'))")
case('TYPE-INTEGER', "assert type(42) is int and 2**100 == 1267650600228229401496703205376",
     "assert int('-0') == 0 and -(2**100) == -1267650600228229401496703205376",
     "rejects(ValueError, lambda: int('1.5'))")
case('TYPE-LIST', "value = [1, 'x', {'y': 2}]\nassert type(value) is list\nvalue[0] = 9\nassert value == [9, 'x', {'y': 2}]",
     "value = []\nvalue.append(None)\nassert value == [None]\nassert value.pop() is None and value == []",
     "rejects(IndexError, lambda: [][0])\nrejects(TypeError, lambda: list(1))")
case('TYPE-STRING', "assert type('text') is str and 'single' == \"single\"\nassert 'café'[3] == 'é'",
     "assert len('') == 0 and len('😀') == 1",
     "rejects(TypeError, lambda: exec(\"value = 'abc'\\nvalue[0] = 'x'\"))")

section('SECTION-2-1-1-002', ['EXAMPLE-001', 'SYNTAX-INDENTED-BLOCK'])
section('SECTION-2-1-2-003', ['EXAMPLE-002', 'EXAMPLE-003', 'EXAMPLE-004',
                           'SYNTAX-MULTILINE-BACKSLASH', 'SYNTAX-MULTILINE-COMMA',
                           'SYNTAX-MULTILINE-STRING-PLUS'])
section('SECTION-2-1-3-004', ['EXAMPLE-005', 'EXAMPLE-006',
                           'SYNTAX-LINE-COMMENT', 'SYNTAX-DOCSTRING-COMMENT'])
section('SECTION-2-1-4-005', ['EXAMPLE-007', 'SYNTAX-DYNAMIC-ASSIGNMENT'])
section('SECTION-2-1-5-006', ['EXAMPLE-008', 'TYPE-INTEGER', 'TYPE-FLOAT', 'TYPE-BOOLEAN',
                           'TYPE-STRING', 'TYPE-LIST', 'TYPE-DICTIONARY',
                           'SYNTAX-LIST-LITERAL', 'SYNTAX-DICTIONARY-LITERAL',
                           'SYNTAX-INDEX', 'SYNTAX-DICTIONARY-LOOKUP'])
section('SECTION-2-1-6-007', ['SYNTAX-CASE-SENSITIVE-NAMES'])
section('SECTION-2-1-7-008', ['EXAMPLE-009'] + [key.removeprefix(PREFIX) for key in cases
    if key.startswith(PREFIX + 'METHOD-MATH-')] + [
        'OPERATOR-PYTHON-' + name for name in
        ('ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'MODULUS', 'POWER', 'BITWISE-AND', 'BITWISE-OR')])
section('SECTION-2-1-8-009', ['EXAMPLE-010'] + [
    'OPERATOR-PYTHON-' + name for name in
    ('AND', 'OR', 'NOT', 'EQUAL', 'NOT-EQUAL', 'LEGACY-NOT-EQUAL', 'LESS',
     'LESS-EQUAL', 'GREATER', 'GREATER-EQUAL')])
section('SECTION-2-1-9-010', ['EXAMPLE-011', 'EXAMPLE-012', 'OPERATOR-STRING-CONCAT',
                           'SYNTAX-INDEX', 'SYNTAX-SLICE'] + [
    key.removeprefix(PREFIX) for key in cases if key.startswith(PREFIX + 'METHOD-STRING-')
    or key.startswith(PREFIX + 'METHOD-CONVERSION-')])
section('SECTION-2-1-10-011', ['EXAMPLE-013', 'SYNTAX-IF-ELIF-ELSE'])
section('SECTION-2-1-11-012', ['EXAMPLE-014', 'EXAMPLE-015', 'SYNTAX-FOR-IN',
                            'SYNTAX-WHILE', 'SYNTAX-BREAK', 'SYNTAX-CONTINUE',
                            'METHOD-CONVERSION-RANGE', 'METHOD-DICTIONARY-KEYS'])
section('SECTION-2-1-12-013', ['EXAMPLE-016', 'EXAMPLE-017',
                            'SYNTAX-FUNCTION-DEFINITION', 'SYNTAX-MULTIPLE-ASSIGNMENT'])
section('SECTION-2-1-13-014', ['EXAMPLE-018', 'SYNTAX-IMPORT', 'SYNTAX-QUALIFIED-ACCESS'])
section('SECTION-2-1-001', [key.removeprefix(PREFIX) for key in cases])


def run():
    assert sys.version_info[:2] == (3, 13), sys.version
    assert 'site-packages/spell/lib/' in spell.lib.__file__.replace('\\', '/'), spell.lib.__file__
    assert REGISTRY['TIME'] is not None
    checks = {}
    for identifier, definition in cases.items():
        for dimension in DIMENSIONS:
            source = definition['sources'][dimension]
            row = dict(dimension=dimension, contracts=[identifier],
                       oracle=definition['oracle'], source=source, passed=False)
            if definition['legacy_spelling_supported'] is False:
                row.update(legacy_spelling_supported=False, evidence_kind='migration-and-rejection')
            namespace = {'__name__': '__python_contract__', 'math': math,
                         'equal': equal, 'rejects': rejects}
            try:
                exec(compile(source, '<' + identifier + ':' + dimension + '>', 'exec'), namespace, namespace)
                row['passed'] = True
            except Exception as error:
                row['error'] = type(error).__name__ + ': ' + str(error)
            checks[identifier + ':' + dimension] = row
    for identifier, members in sections.items():
        for dimension in DIMENSIONS:
            dependencies = [member + ':' + dimension for member in members]
            checks[identifier + ':' + dimension] = dict(
                dimension=dimension, contracts=[identifier],
                passed=all(checks[key]['passed'] for key in dependencies),
                oracle='Every explicitly listed child contract must pass its independently asserted ' + dimension + ' case. Legacy child evidence remains migration/rejection, not supported original spelling.',
                dependencies=dependencies)
    report = dict(checks=checks, interpreter=sys.version,
                  platform=platform.platform(), machine=platform.machine(),
                  spell_library=spell.lib.__file__, semantics='CPython 3.13',
                  legacy_contracts={PREFIX + suffix: 'Original Python 2 spelling unsupported; migration/rejection evidence only'
                                    for suffix in sorted(LEGACY)},
                  checkpoint_claim=False)
    Path('python-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PYTHON_CONFORMANCE_RESULT', sum(row['passed'] for row in checks.values()), len(checks), flush=True)
    return


run()
