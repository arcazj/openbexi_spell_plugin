"""Independent LRM 2.4.4 pp.32-35 oracles, executed inside original native SPELL.

The test clock replaces only the original example driver's UTC input. No
language methods, native types, factory, registry or executor are replaced.
"""
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import time

from spell.lib.adapter.utctime import TIME, NOW, TODAY, TOMORROW, YESTERDAY, HOUR, MINUTE, SECOND
from spell.lib.exception import DriverException
from spell.lib.registry import REGISTRY


PREFIX = 'CMP-LRM244-'
cases = {}
clock = [datetime(2000, 2, 29, 23, 59, 59, 125000)]
driver = REGISTRY['TIME']
original_clock = driver._getUTC
driver._getUTC = lambda *args, **kwargs: clock[0]
original_tz = os.environ.get('TZ')


def equal(actual, expected):
    if isinstance(expected, list) and isinstance(actual, list):
        assert len(actual) == len(expected)
        for value, want in zip(actual, expected):
            equal(value, want)
        return
    if type(actual) is float and type(expected) is float:
        assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12), (actual, expected)
        return
    assert actual == expected, f'expected {expected!r}, got {actual!r}'


def rejects(operation, exceptions=(DriverException, TypeError, ValueError, OverflowError)):
    try:
        operation()
    except exceptions:
        return
    raise AssertionError('invalid operation returned normally')


def invalid_then_valid():
    rejects(lambda: TIME('not a time'))
    equal(TIME('2000-02-29 12:34:56').value(), datetime(2000, 2, 29, 12, 34, 56))


def case(suffix, positive, boundary, failure, recovery=None, oracle='LRM 2.4.4 pp.32-35; independent datetime/literal expectations'):
    if recovery is None:
        recovery = lambda:(failure(),positive())
    cases[PREFIX + suffix] = dict(positive=positive,boundary=boundary,failure=failure,recovery=recovery,oracle=oracle)


# Each format has an independent literal, leap-day boundary and invalid-date oracle.
for suffix, pattern in (
    ('DMY','%d-%b-%Y'), ('YMD','%Y-%m-%d'), ('SLASH','%d/%m/%Y'),
    ('COLON-DMY','%d-%b-%Y:'), ('COLON-YMD','%Y-%m-%d:'), ('COLON-SLASH','%d/%m/%Y:'),
):
    separator = '' if pattern.endswith(':') else ' '
    positive = datetime(2008, 5, 21, 10, 30, 25).strftime(pattern + separator + '%H:%M:%S')
    boundary = datetime(2000, 2, 29, 23, 59).strftime(pattern + separator + '%H:%M')
    invalid = datetime(2000, 2, 29, 23, 59).strftime(pattern + separator + '%H:%M').replace('2000','1900')
    case('SYNTAX-ABSOLUTE-TIME-' + suffix,
         lambda text=positive: equal(TIME(text).value(), datetime(2008,5,21,10,30,25)),
         lambda text=boundary: equal(TIME(text).value(), datetime(2000,2,29,23,59)),
         lambda text=invalid: rejects(lambda: TIME(text)))


case('SYNTAX-RELATIVE-TIME-SECONDS',
     lambda: equal(TIME('+23.500').rel(),23.5),
     lambda: equal([TIME('-0.000001').rel(),TIME('+0').rel()],[-.000001,0]),
     lambda: rejects(lambda: TIME('+nan')),
     lambda: (rejects(lambda: TIME('-inf')),equal(TIME('-23.500').rel(),-23.5)))
case('SYNTAX-RELATIVE-TIME-DAYS',
     lambda: equal(TIME('+001 23:10:30').rel(),169830),
     lambda: equal([TIME('+001 23:10').rel(),TIME('-001 23:10').rel()],[169800,-169800]),
     lambda: rejects(lambda: TIME('+001 invalid')),
     lambda: (rejects(lambda: TIME('+001 bad')),equal(TIME('-001 23:10:30').rel(),-169830)))

for name, constant, seconds in (('HOUR',HOUR,3600),('MINUTE',MINUTE,60),('SECOND',SECOND,1)):
    case('CONSTANT-TIME-' + name,
         lambda value=constant,expected=seconds: equal(value.rel(),expected),
         lambda value=constant: equal((value*0).rel(),0),
         lambda value=constant: rejects(lambda:value * object()),
         lambda value=constant,expected=seconds: (rejects(lambda:value * object()),equal((2*value).rel(),2*expected)))


def moving_now():
    observed = NOW
    first = observed.value()
    clock[0] += timedelta(seconds=1)
    equal(observed.value(), first + timedelta(seconds=1))


def fixed_now():
    observed = TIME(NOW)
    first = observed.value()
    clock[0] += timedelta(days=1)
    equal(observed.value(),first)


def failed_clock():
    driver._getUTC = lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('clock unavailable'))
    rejects(lambda:NOW.value(),(RuntimeError,DriverException))


def clock_recovery():
    try:
        failed_clock()
    finally:
        driver._getUTC = lambda *args,**kwargs: clock[0]
    equal(NOW.value(),clock[0])


for name, constant, days in (('TODAY',TODAY,0),('TOMORROW',TOMORROW,1),('YESTERDAY',YESTERDAY,-1)):
    def day_boundary(value=constant, offset=days):
        clock[0] = datetime(2000,3,1,0,0,0)
        equal(value.value(),datetime(2000,3,1) + timedelta(days=offset))
    case('CONSTANT-TIME-' + name,
         lambda value=constant,offset=days: equal(value.value(),datetime(2000,2,29) + timedelta(days=offset)),
         day_boundary, failed_clock,
         lambda value=constant,offset=days:(clock_recovery(),equal(value.value(),datetime(2000,2,29)+timedelta(days=offset))))
for suffix, function in (('CONSTANT-TIME-NOW',moving_now),('EXAMPLE-026',moving_now),('EXAMPLE-027',fixed_now)):
    def midnight_boundary(operation=function):
        clock[0] = datetime(1999,12,31,23,59,59)
        operation()
    case(suffix,function,midnight_boundary,failed_clock,lambda operation=function:(clock_recovery(),operation()))


def abs_utc():
    equal(TIME('2006/04/02 20:32:34').abs(),1144009954.0)


def abs_boundary():
    os.environ['TZ'] = 'UTC+05'
    time.tzset()
    equal(TIME('1970-01-01 00:00:00.125').abs(),.125)


case('METHOD-TIME-ABS',abs_utc,abs_boundary,lambda:rejects(lambda:TIME('invalid').abs()),
     oracle='UTC epoch from calendar.timegm; manual example 29 epoch is two hours inconsistent with its UTC rule')
case('METHOD-TIME-REL',lambda:equal(TIME('+00:00:30').rel(),30),
     lambda:equal([TIME(-.125).rel(),TIME('2000-02-29').rel()],[-.125,None]),
     lambda:rejects(lambda:TIME('invalid').rel()))
case('METHOD-TIME-ISREL',lambda:equal(TIME(1).isRel(),True),
     lambda:equal([TIME(0).isRel(),TIME('2000-02-29').isRel()],[True,False]),
     lambda:rejects(lambda:TIME('invalid').isRel()))

for name,expected,boundary in (('year',2006,2000),('month',4,2),('hour',20,23),('minute',32,59),('second',34,59),('julianDay',92,60)):
    case('METHOD-TIME-' + name.upper(),
         lambda method=name,want=expected:equal(getattr(TIME('2006/04/02 20:32:34'),method)(),want),
         lambda method=name,want=boundary:equal(getattr(TIME('2000-02-29 23:59:59'),method)(),want),
         lambda method=name:equal(getattr(TIME(0),method)(),None))


def change_format(pattern='%Y/%m/%d %H:%M:%S',expected='2006/04/02 20:32:34'):
    TIME.fmt(pattern)
    equal(str(TIME('2006-04-02 20:32:34')),expected)
    equal(repr(TIME('2006-04-02 20:32:34')),expected)


def bad_format():
    def operation():
        TIME.fmt(123)
        str(TIME('2000-02-29'))
    rejects(operation)


def format_recovery():
    bad_format()
    change_format()


for suffix in ('METHOD-TIME-FMT','EXAMPLE-028'):
    case(suffix,change_format,lambda:(TIME.fmt('%Y'),equal(TIME('+00:00:30').rel(),30)),bad_format,format_recovery)
for name,pattern,expected,boundary in (
    ('DAY','%d','02','29'), ('MONTH-ABBREVIATED','%b','Apr','Feb'),('MONTH-NUMERIC','%m','04','02'),
    ('YEAR','%Y','2006','2000'),('HOUR','%H','20','23'),('MINUTE','%M','32','59'),('SECOND','%S','34','59'),
):
    case('SYNTAX-TIME-OUTPUT-' + name,
         lambda fmt=pattern,want=expected:change_format(fmt,want),
         lambda fmt=pattern,want=boundary:(TIME.fmt(fmt),equal(str(TIME('2000-02-29 23:59:59')),want)),
         bad_format,lambda fmt=pattern,want=expected:(bad_format(),change_format(fmt,want)))

case('OPERATOR-TIME-ADD',
     lambda:equal((TIME('2000-02-29 23:59:59') + SECOND).value(),datetime(2000,3,1)),
     lambda:equal((TIME(-1) + SECOND).rel(),0),
     lambda:rejects(lambda:TIME('2000-01-01')+TIME('2000-01-01')))
case('OPERATOR-TIME-SUBTRACT',
     lambda:equal((TIME('2000-03-01') - TIME('2000-02-29')).rel(),86400),
     lambda:equal((10 - TIME(4)).rel(),6),
     lambda:rejects(lambda:TIME(1)-TIME('2000-01-01')))
case('OPERATOR-TIME-MULTIPLY',lambda:equal((3*HOUR).rel(),10800),
     lambda:equal([(TIME(1)*0).rel(),(TIME(1)*-2).rel()],[0,-2]),
     lambda:rejects(lambda:TIME('2000-01-01')*2,(AttributeError,DriverException,TypeError)))


def example_29():
    absolute, relative = TIME('2006/04/02 20:32:34'), TIME('+00:00:30')
    equal(absolute.abs(),1144009954.0)
    equal(relative.rel(),30)
    equal((absolute + relative).value(),datetime(2006,4,2,20,33,4))
    # p.34 defines the default format; p.35's slash output presumes a fmt call.
    equal(str(absolute),'02-Apr-2006 20:32:34')


case('EXAMPLE-029',example_29,abs_boundary,lambda:rejects(lambda:TIME('1900-02-29')))


checks = {}
try:
    for identifier, functions in cases.items():
        for dimension in ('positive','boundary','failure','recovery'):
            clock[0] = datetime(2000,2,29,23,59,59,125000)
            driver._getUTC = lambda *args,**kwargs:clock[0]
            TIME.fmt('%d-%b-%Y %H:%M:%S')
            os.environ['TZ'] = 'UTC'
            time.tzset()
            row = {'dimension':dimension,'contracts':[identifier], 'oracle':functions['oracle'], 'passed':False}
            try:
                functions[dimension]()
                row['passed'] = True
            except Exception as error:
                row['error'] = type(error).__name__ + ': ' + str(error)
            checks[identifier + ':' + dimension] = row
    # Broad sections/type are qualified only when every contained oracle passed.
    for suffix in ('TYPE-TIME','SECTION-4-1-022','SECTION-4-1-1-023'):
        identifier = PREFIX + suffix
        for dimension in ('positive','boundary','failure','recovery'):
            relevant = [row for row in checks.values() if row['dimension']==dimension]
            checks[identifier + ':' + dimension] = {'dimension':dimension,'contracts':[identifier],
                'oracle':'All contained independently specified TIME oracles must pass',
                'passed':all(row['passed'] for row in relevant)}
finally:
    driver._getUTC = original_clock
    TIME.fmt('%d-%b-%Y %H:%M:%S')
    if original_tz is None:
        os.environ.pop('TZ',None)
    else:
        os.environ['TZ'] = original_tz
    time.tzset()
Path('time-results.json').write_text(json.dumps({'checks':checks},indent=2)+'\n',encoding='utf-8')
print('TIME_CONFORMANCE_RESULT',sum(row['passed'] for row in checks.values()),len(checks),flush=True)
