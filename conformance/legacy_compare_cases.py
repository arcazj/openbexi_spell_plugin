"""Literal native procedure oracles for the legacy p21 comparison operator."""
FIXTURE = '''class Broken:
    def __ne__(self, other):
        raise ValueError('INTENTIONAL_COMPARISON_FAILURE')

def rejects(kind, operation):
    try:
        operation()
    except kind as error:
        assert str(error) == 'INTENTIONAL_COMPARISON_FAILURE'
        return
    raise AssertionError('Expected ' + kind.__name__)
'''

CASES = {
    'positive': "assert (1 <> 2) is True\nassert (2 <> 2) is False\n",
    'boundary': "assert (0 <> False) is False\nassert ([] <> []) is False\nassert ([1] <> [2]) is True\nassert (-10**100 <> 10**100) is True\nassert (float('nan') <> float('nan')) is True\n",
    'failure': "import comparison_fixture as fixture\nfixture.rejects(ValueError, lambda: fixture.Broken() <> 1)\n",
    'recovery': "import comparison_fixture as fixture\nfixture.rejects(ValueError, lambda: fixture.Broken() <> 1)\nassert (1 <> 2) is True\nassert ('same' <> 'same') is False\n",
    'strings-comments': '''# Preserve <> literally in strings and comments.
assert "<>" == '<>' and b'<>' == bytes([60, 62])
assert r"<>" == '<>'
assert """before
<>
after""" == 'before\\n<>\\nafter'
assert (1 <> 2) is True
''',
    'unicode': "café = '通信'; assert (café <> 'other') is True\nassert ('\u2028<>' <> '<>') is True\n",
    'multiline': "assert (\n 1 <> 2\n)\nassert 1 \\\n <> 2\n",
    'nested-functions': "def outer():\n    def inner(value):\n        return value <> 2\n    return inner(1) and not inner(2)\nassert outer() is True\n",
    'mixed-modern': "assert (1 <> 2) and (2 != 3) and (2 >= 2) and (1 <= 1)\nassert f'{1 <> 2} <>' == 'True <>'\n",
    'chain': "assert (1 <> 2 <> 1) is True\nassert (1 <> 1 <> 2) is False\n",
    'goto': "from spell.lang.functions import Step, Goto\nvisited = []\nStep('INIT', 'start')\nif 1 <> 2:\n    Goto('END')\nvisited.append('unexpected fallthrough')\nStep('END', 'finish')\nassert visited == []\nassert (2 <> 2) is False\n",
    'modern-control': "assert (1 != 2) is True\nassert '<>' == chr(60) + chr(62)\n",
}

INVALID = {'spaced-operator': 'result = 1 < > 2\n', 'missing-right-operand': 'result = 1 <>\n',
           'incomplete-group': 'result = (1 <> 2\n'}
