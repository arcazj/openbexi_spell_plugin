"""Explicit Python 2 built-in value semantics for reviewed migrated sources."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
from itertools import zip_longest


def legacy_divide(left, right):
    if isinstance(left, int) and isinstance(right, int):
        return left // right
    if type(left) in {int, float, bool} and type(right) in {int, float, bool}:
        return left / right
    raise TypeError("legacy division of custom objects requires manual migration")


def legacy_range(*args):
    return list(range(*args))


def legacy_round(number, ndigits=0):
    if type(number) not in {int, float, bool} or type(ndigits) is not int:
        raise TypeError("legacy round requires a built-in number and integer precision")
    number = float(number)
    if not math.isfinite(number):
        raise ValueError("legacy round of nonfinite values requires manual migration")
    if ndigits > 308:
        return number
    if ndigits < -308:
        return math.copysign(0.0, number)
    with localcontext() as context:
        context.prec = 1100
        return float(Decimal.from_float(number).quantize(Decimal(1).scaleb(-ndigits), rounding=ROUND_HALF_UP))


def legacy_list(value):
    return list(value)


def legacy_unicode(value='',encoding=None,errors='strict'):
    if isinstance(value,bytes):return value.decode(encoding or 'ascii',errors)
    if encoding is not None:raise TypeError('encoding requires byte input')
    return str(value)

def legacy_map(function,*iterables):
    if not iterables:raise TypeError('map requires an iterable')
    if function is None:
        return list(iterables[0]) if len(iterables)==1 else list(zip_longest(*iterables))
    return [function(*values) for values in zip_longest(*iterables)]

def legacy_filter(function,sequence):
    values=[v for v in sequence if (function(v) if function is not None else v)]
    return ''.join(values) if type(sequence) is str else tuple(values) if type(sequence) is tuple else values

def legacy_zip(*iterables):return list(zip(*iterables))
legacy_long, legacy_basestring, legacy_xrange = int, (str, bytes), range
