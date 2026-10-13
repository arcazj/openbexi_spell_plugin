"""LRM shared blackboard and native data oracles; no service substitutions."""
import json
from pathlib import Path
import uuid

from spell.lang.functions import (
    AddSharedDataScope, ClearSharedData, ClearSharedDataScopes, GetSharedData,
    GetSharedDataKeys, GetSharedDataScopes, SetSharedData,
)
from spell.lang.constants import GLOBAL
from spell.lib.exception import DriverException, SyntaxException

PREFIX = 'CMP-LRM244-'
DIMENSIONS = ('positive', 'boundary', 'failure', 'recovery')
cases = {}
checks = {}


def eq(actual, expected):
    assert actual == expected and type(actual) is type(expected), (actual, expected)


def rejects(operation, kind=DriverException):
    try:
        operation()
    except kind:
        return
    raise AssertionError('Expected ' + kind.__name__)


def call(function, *args, **kwargs):
    return function(*args, HandleError=False, **kwargs)


def scope():
    name = 'data-owned-' + uuid.uuid4().hex
    eq(call(AddSharedDataScope, name), True)
    return name


def case(name, contracts, positive, boundary, failure, recovery=None):
    cases[name] = dict(contracts=[PREFIX+item for item in contracts], positive=positive,
        boundary=boundary, failure=failure, recovery=recovery or (lambda: (failure(), positive())),
        oracle='LRM 2.4.4 pp.95-99: literal typed values, scope isolation and compare-and-set outcomes through original native CIF and context blackboard')


def primitives_positive():
    s = scope()
    values = [123, -42, 1.25, 'text', True, False, [1,'two',False], {'a':[1,2], 'b':True}]
    for value in values:
        eq(call(SetSharedData, ['value', value], Scope=s), True)
        actual = call(GetSharedData, 'value', Scope=s)
        eq(actual, value)
    eq(call(ClearSharedDataScopes, s), True)


def primitives_boundary():
    s = scope()
    for value in (0, '', [], {}, 2**63-1, -2**63, 'café λ', [[[]]], {'empty':[]}):
        eq(call(SetSharedData, Name='value', Value=value, Scope=s), True)
        eq(call(GetSharedData, 'value', Scope=s), value)
    call(ClearSharedDataScopes, s)


def primitives_failure():
    s = scope()
    call(SetSharedData, Name='value', Value=42, Scope=s)
    for value in (None, object(), (1,2), {'invalid':object()}, [1,object()]):
        rejects(lambda: call(SetSharedData, Name='value', Value=value, Scope=s), SyntaxException)
        eq(call(GetSharedData, 'value', Scope=s), 42)
    for args in ([], ['only-name'], [['name']], [['name',1,2,3]]):
        rejects(lambda: call(SetSharedData, args, Scope=s), SyntaxException)
    call(ClearSharedDataScopes, s)


case('primitive-values', ['FUNCTION-SETSHAREDDATA', 'EXAMPLE-177', 'EXAMPLE-178',
    'TYPE-PRIMITIVESHAREDVALUE', 'SECTION-4-19-1-130'],
    primitives_positive, primitives_boundary, primitives_failure)


def batches_positive():
    s = scope()
    eq(call(SetSharedData, [['a', 10], ['b', 20]], Scope=s), [True, True])
    eq(call(GetSharedData, ['b', 'a'], Scope=s), [20, 10])
    eq(call(SetSharedData, [['a', 11, 10], ['b', 21, -1]], Scope=s), [True, False])
    eq(call(GetSharedData, ['a','b'], Scope=s), [11,20])
    call(ClearSharedDataScopes, s)


def batches_boundary():
    s = scope()
    eq(call(SetSharedData, [['only', []]], Scope=s), [True])
    eq(call(GetSharedData, ['only'], Scope=s), [[]])
    eq(call(SetSharedData, [['only', [42], []]], Scope=s), [True])
    eq(call(GetSharedData, 'only', Scope=s), [42])
    call(ClearSharedDataScopes, s)


def batches_failure():
    s = scope()
    call(SetSharedData, [['a',1], ['b',2]], Scope=s)
    rejects(lambda: call(SetSharedData, [['a',3], ['b',object()]], Scope=s), SyntaxException)
    eq(call(GetSharedData, ['a','b'], Scope=s), [1,2])
    rejects(lambda: call(GetSharedData, ['a','absent'], Scope=s))
    call(ClearSharedDataScopes, s)


case('batch-values', ['EXAMPLE-179', 'EXAMPLE-183', 'EXAMPLE-185'],
    batches_positive, batches_boundary, batches_failure)


def compare_positive():
    s = scope()
    call(SetSharedData, ['count',10], Scope=s)
    eq(call(SetSharedData, ['count',11,10], Scope=s), True)
    eq(call(GetSharedData, 'count', Scope=s), 11)
    eq(call(SetSharedData, Name='count',Value=12,Expected=11,Scope=s), True)
    eq(call(GetSharedData, 'count', Scope=s), 12)
    call(ClearSharedDataScopes, s)


def compare_boundary():
    s = scope()
    call(SetSharedData, ['item', []], Scope=s)
    eq(call(SetSharedData, ['item', [0]], Expected=[], Scope=s), True)
    eq(call(SetSharedData, ['item', [0], [0]], Scope=s), True)
    eq(call(GetSharedData, 'item', Scope=s), [0])
    call(ClearSharedDataScopes, s)


def compare_failure():
    s = scope()
    call(SetSharedData, ['item',7], Scope=s)
    eq(call(SetSharedData, ['item',8,6], Scope=s), False)
    eq(call(GetSharedData, 'item', Scope=s), 7)
    eq(call(SetSharedData, Name='item',Value=9,Expected='7',Scope=s), False)
    eq(call(GetSharedData, 'item', Scope=s), 7)
    call(ClearSharedDataScopes, s)


case('compare-and-set', ['EXAMPLE-182', 'SYNTAX-SHARED-TEST-AND-SET',
    'SECTION-4-19-2-131'], compare_positive, compare_boundary, compare_failure)


def scopes_positive():
    left, right = scope(), scope()
    eq(call(SetSharedData, 'name', 1, Scope=left), True)
    eq(call(SetSharedData, Name='name', Value=2, Scope=right), True)
    eq(call(GetSharedData, 'name', Scope=left), 1)
    eq(call(GetSharedData, 'name', Scope=right), 2)
    assert left in call(GetSharedDataScopes) and right in call(GetSharedDataScopes)
    eq(call(GetSharedDataKeys, Scope=left), ['name'])
    call(ClearSharedDataScopes, left)
    call(ClearSharedDataScopes, right)


def scopes_boundary():
    s = scope()
    eq(call(GetSharedDataKeys, Scope=s), [])
    call(SetSharedData, Name='last', Value='', Scope=s)
    eq(call(GetSharedData, 'last', Scope=s), '')
    call(ClearSharedData, Scope=s)
    eq(call(GetSharedDataKeys, Scope=s), [])
    assert s in call(GetSharedDataScopes)
    call(ClearSharedDataScopes, s)


def scopes_failure():
    missing = 'absent-' + uuid.uuid4().hex
    rejects(lambda: call(SetSharedData, Name='name', Value=1, Scope=missing))
    rejects(lambda: call(GetSharedData, 'name', Scope=missing))
    rejects(lambda: call(GetSharedDataKeys, Scope=missing))
    s = scope()
    rejects(lambda: call(GetSharedData, 'absent', Scope=s))
    eq(call(GetSharedDataKeys, Scope=s), [])
    call(ClearSharedDataScopes, s)


case('scope-isolation', ['FUNCTION-ADDSHAREDDATASCOPE','FUNCTION-GETSHAREDDATA',
    'FUNCTION-GETSHAREDDATAKEYS','FUNCTION-GETSHAREDDATASCOPES',
    'EXAMPLE-180','EXAMPLE-181','EXAMPLE-184','EXAMPLE-186','EXAMPLE-187',
    'SECTION-4-19-3-132'], scopes_positive, scopes_boundary, scopes_failure)


def clear_positive():
    left, right = scope(), scope()
    call(SetSharedData, [['a',1],['b',2],['c',3]], Scope=left)
    call(SetSharedData, ['a',9], Scope=right)
    eq(call(ClearSharedData, ['a','b'], Scope=left), [True, True])
    eq(call(GetSharedDataKeys, Scope=left), ['c'])
    eq(call(GetSharedData, 'a', Scope=right), 9)
    eq(call(ClearSharedData, 'c', Scope=left), True)
    eq(call(GetSharedDataKeys, Scope=left), [])
    eq(call(ClearSharedDataScopes, Scope=left), True)
    assert left not in call(GetSharedDataScopes)
    eq(call(GetSharedData, 'a', Scope=right), 9)
    call(ClearSharedDataScopes, right)


def clear_boundary():
    s = scope()
    eq(call(ClearSharedData, Scope=s), True)
    call(SetSharedData, ['a',1], Scope=s)
    eq(call(ClearSharedData, Scope=s), True)
    eq(call(GetSharedDataKeys, Scope=s), [])
    call(ClearSharedDataScopes, s)


def clear_failure():
    s = scope()
    call(SetSharedData, ['retained',42], Scope=s)
    rejects(lambda: call(ClearSharedDataScopes, Scope=42), SyntaxException)
    eq(call(GetSharedData, 'retained', Scope=s), 42)
    rejects(lambda: call(ClearSharedData, Scope='missing-' + uuid.uuid4().hex))
    eq(call(GetSharedData, 'retained', Scope=s), 42)
    call(ClearSharedDataScopes, s)


case('clear-scopes', ['FUNCTION-CLEARSHAREDDATA','FUNCTION-CLEARSHAREDDATASCOPES',
    'EXAMPLE-188','EXAMPLE-189','SECTION-4-19-4-133'],
    clear_positive, clear_boundary, clear_failure)


def global_positive():
    key = 'global-' + uuid.uuid4().hex
    call(SetSharedData, [key,42])
    eq(call(GetSharedData, key, Scope=GLOBAL), 42)
    eq(call(ClearSharedData, key), True)
    assert key not in call(GetSharedDataKeys, Scope=GLOBAL)


def global_boundary():
    # Each test runs in a new isolated native context; no other users share it.
    call(SetSharedData, Name='owned-global', Value=1)
    eq(call(ClearSharedData, Scope=GLOBAL), True)
    eq(call(GetSharedDataKeys), [])
    s = scope()
    eq(call(ClearSharedDataScopes), True)
    assert s not in call(GetSharedDataScopes)
    eq(call(GetSharedDataKeys, Scope=GLOBAL), [])


def global_failure():
    # Original 2.6.10 acknowledges the forbidden deletion as an idempotent
    # no-op. The global table and its values must survive the attempt.
    call(SetSharedData, Name='retained-global',Value=17, Scope=GLOBAL)
    eq(call(ClearSharedDataScopes, GLOBAL), True)
    eq(call(GetSharedData,'retained-global',Scope=GLOBAL),17)
    call(ClearSharedData,'retained-global')
    call(SetSharedData, Name='recovered',Value=42, Scope=GLOBAL)
    eq(call(GetSharedData, 'recovered'),42)
    call(ClearSharedData,'recovered')


case('global-scope', ['CONSTANT-SCOPE-GLOBAL','EXAMPLE-190','SECTION-4-19-5-134'],
    global_positive, global_boundary, global_failure)


for name, spec in cases.items():
    for dimension in DIMENSIONS:
        identifier = name+':'+dimension
        row = {key: spec[key] for key in ('contracts','oracle')}
        row.update(dimension=dimension, passed=False, expected_prompts=[])
        Path('data-files-active.json').write_text(json.dumps({'check':identifier,'prompts':[]}),encoding='utf-8')
        try:
            spec[dimension]()
            row['passed'] = True
        except Exception as error:
            row['error'] = type(error).__name__ + ': ' + str(error)
        checks[identifier] = row
        Path('data-files-results.json').write_text(json.dumps({'schema':1,'checks':checks},indent=2),encoding='utf-8')

Path('data-files-results.json').write_text(json.dumps({'schema':1,'checks':checks},indent=2),encoding='utf-8')
