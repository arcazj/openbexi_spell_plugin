"""UTC TIME values from Language Reference 2.4.4, pp. 32-35.

Dynamic calendar constants are evaluated on use; constructing TIME from one
captures its current value. Clock and output format are local to the context.
No host-local timezone, locale or floating-point epoch arithmetic is used.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

UTC = timezone.utc
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_clock = ContextVar("spell_utc_clock", default=lambda: datetime.now(UTC))
_format = ContextVar("spell_time_output_format", default="%d-%b-%Y %H:%M:%S")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_DIRECTIVES = frozenset("aAbBcdHIjmMpSUwWxXyYfzZGuV%")


def _utc_now():
    value = _clock.get()()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("SPELL clock must return an aware UTC datetime")
    return value.astimezone(UTC)


def _duration(value):
    if type(value) not in {int, float, Decimal}:
        raise TypeError("relative TIME seconds must be numeric")
    try:
        seconds = Decimal(str(value))
        if not seconds.is_finite():
            raise ValueError("TIME must be finite")
        micros = seconds * 1_000_000
        if micros != micros.to_integral_value():
            raise ValueError("TIME precision exceeds one microsecond")
        return timedelta(microseconds=int(micros))
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("TIME is outside its supported range") from exc


def _parse(text):
    if not text or text != text.strip() or len(text) > 128:
        raise ValueError("invalid TIME string")
    if text[0] in "+-":
        sign = -1 if text[0] == "-" else 1
        body = text[1:]
        if re.fullmatch(r"\d+(?:\.\d{1,6})?", body):
            return _duration(Decimal(body) * sign)
        match = re.fullmatch(r"(?:(\d+) )?(\d+):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?", body)
        if match is None:
            raise ValueError("invalid relative TIME format")
        days, hours, minutes, seconds, fraction = match.groups()
        hours, minutes, seconds = int(hours), int(minutes), int(seconds or "0")
        if minutes >= 60 or seconds >= 60 or (days is not None and hours >= 24):
            raise ValueError("relative TIME component is outside its range")
        return sign * timedelta(days=int(days or "0"), hours=hours, minutes=minutes,
                                seconds=seconds, microseconds=int((fraction or "").ljust(6, "0") or "0"))
    # The YYYY/MM/DD spelling in Example 29 is an explicit supported extension.
    patterns = (
        (r"(\d{4})-(\d{2})-(\d{2})", "ymd"),
        (r"(\d{4})/(\d{2})/(\d{2})", "ymd"),
        (r"(\d{2})/(\d{2})/(\d{4})", "dmy"),
        (r"(\d{2})-([A-Za-z]{3})-(\d{4})", "named"),
    )
    for pattern, order in patterns:
        match = re.fullmatch(pattern + r"(?:[ :T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?Z?", text)
        if match is None:
            continue
        first, middle, last, hour, minute, second, fraction = match.groups()
        if order == "named":
            months = {name.lower(): index + 1 for index, name in enumerate(_MONTHS)}
            if middle.lower() not in months:
                raise ValueError("invalid TIME month")
            year, month, day = int(last), months[middle.lower()], int(first)
        elif order == "dmy":
            year, month, day = int(last), int(middle), int(first)
        else:
            year, month, day = int(first), int(middle), int(last)
        return datetime(year, month, day, int(hour or "0"), int(minute or "0"),
                        int(second or "0"), int((fraction or "").ljust(6, "0") or "0"), tzinfo=UTC)
    raise ValueError("invalid absolute TIME format")


def _render(value, fmt):
    weekday, ordinal = value.weekday(), value.timetuple().tm_yday
    iso_year, iso_week, iso_day = value.isocalendar()
    fields = {"d": f"{value.day:02d}", "b": _MONTHS[value.month - 1], "m": f"{value.month:02d}",
              "Y": f"{value.year:04d}", "H": f"{value.hour:02d}", "M": f"{value.minute:02d}",
              "S": f"{value.second:02d}", "f": f"{value.microsecond:06d}",
              "j": f"{ordinal:03d}", "%": "%", "a": _DAYS[weekday][:3], "A": _DAYS[weekday],
              "B": _MONTH_NAMES[value.month - 1], "I": f"{value.hour % 12 or 12:02d}",
              "p": "AM" if value.hour < 12 else "PM", "w": str((weekday + 1) % 7),
              "U": f"{(ordinal + 6 - (weekday + 1) % 7) // 7:02d}",
              "W": f"{(ordinal + 6 - weekday) // 7:02d}", "y": f"{value.year % 100:02d}",
              "z": "+0000", "Z": "UTC", "G": f"{iso_year:04d}", "u": str(iso_day), "V": f"{iso_week:02d}",
              "x": f"{value.month:02d}/{value.day:02d}/{value.year % 100:02d}",
              "X": f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"}
    fields["c"] = f"{fields['a']} {fields['b']} {value.day:2d} {fields['X']} {fields['Y']}"
    return re.sub(r"%(.)", lambda match: fields[match[1]], fmt)


class TIME:
    __slots__ = ("_stored", "_dynamic")
    __hash__ = None  # A dynamic NOW value cannot be a stable dictionary key.

    def __init__(self, value):
        if isinstance(value, TIME):
            value = value.value()
        elif type(value) is str:
            value = _parse(value)
        elif type(value) in {int, float, Decimal}:
            value = _duration(value)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("absolute TIME requires an aware datetime")
            value = value.astimezone(UTC)
        if not isinstance(value, (datetime, timedelta)):
            raise TypeError("TIME requires a string, TIME, aware datetime or relative seconds")
        self._stored, self._dynamic = value, None

    @classmethod
    def _calendar(cls, day_offset=None):
        value = cls(0)
        def current():
            now = _utc_now()
            return now if day_offset is None else now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
        value._dynamic = current
        return value

    @staticmethod
    def fmt(value=None):
        if value is not None:
            if type(value) is not str or not value or len(value) > 256:
                raise ValueError("invalid TIME output format")
            position = 0
            while position < len(value):
                if value[position] == "%":
                    position += 1
                    if position == len(value) or value[position] not in _DIRECTIVES:
                        raise ValueError("unsupported TIME output format directive")
                position += 1
            _format.set(value)
        return _format.get()

    @staticmethod
    def epoch(seconds):
        return TIME(_EPOCH + _duration(seconds))

    def value(self):
        return self._dynamic() if self._dynamic is not None else self._stored

    def abs(self):
        value = self.value()
        if isinstance(value, timedelta):
            value = _utc_now() + value
        return (value - _EPOCH).total_seconds()

    def rel(self):
        value = self.value()
        return value.total_seconds() if isinstance(value, timedelta) else None

    def isRel(self):
        return isinstance(self.value(), timedelta)

    def isAbs(self):
        return not self.isRel()

    def _absolute(self):
        value = self.value()
        if not isinstance(value, datetime):
            raise TypeError("calendar fields require absolute TIME")
        return value

    def julianDay(self):
        return self._absolute().timetuple().tm_yday

    def year(self):
        return self._absolute().year

    def month(self):
        return self._absolute().month

    def day(self):
        return self._absolute().day

    def hour(self):
        return self._absolute().hour

    def minute(self):
        return self._absolute().minute

    def second(self):
        return self._absolute().second

    def millisecond(self):
        return self._absolute().microsecond // 1000

    def microsecond(self):
        return self._absolute().microsecond

    def __str__(self):
        value = self.value()
        if isinstance(value, datetime):
            return _render(value, _format.get())
        micros = (value.days * 86400 + value.seconds) * 1_000_000 + value.microseconds
        sign, magnitude = ("-" if micros < 0 else "+"), abs(micros)
        seconds, fraction = divmod(magnitude, 1_000_000)
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        prefix = f"{days:03d} " if days else ""
        suffix = "." + f"{fraction:06d}".rstrip("0") if fraction else ""
        return f"{sign}{prefix}{hours:02d}:{minutes:02d}:{seconds:02d}{suffix}"

    __repr__ = __str__

    def __add__(self, other):
        left = self.value()
        right = other.value() if isinstance(other, TIME) else _duration(other)
        if isinstance(left, datetime) and isinstance(right, datetime):
            raise TypeError("two absolute TIME values cannot be added")
        return TIME(left + right)

    __radd__ = __add__

    def __sub__(self, other):
        left = self.value()
        right = other.value() if isinstance(other, TIME) else _duration(other)
        if isinstance(left, timedelta) and isinstance(right, datetime):
            raise TypeError("absolute TIME cannot be subtracted from a relative TIME")
        return TIME(left - right)

    def __rsub__(self, other):
        return TIME(other) - self

    def __mul__(self, factor):
        value = self.value()
        if not isinstance(value, timedelta) or type(factor) is not int:
            raise TypeError("only relative TIME multiplied by an integer is supported")
        return TIME(value * factor)

    __rmul__ = __mul__

    def _compare(self, other, operation):
        if not isinstance(other, TIME):
            return NotImplemented
        left, right = self.value(), other.value()
        if type(left) is not type(right):
            raise TypeError("absolute and relative TIME cannot be compared")
        return operation(left, right)

    def __eq__(self, other):
        return self._compare(other, lambda left, right: left == right)

    def __lt__(self, other):
        return self._compare(other, lambda left, right: left < right)

    def __le__(self, other):
        return self._compare(other, lambda left, right: left <= right)

    def __gt__(self, other):
        return self._compare(other, lambda left, right: left > right)

    def __ge__(self, other):
        return self._compare(other, lambda left, right: left >= right)


NOW = TIME._calendar()
TODAY = TIME._calendar(0)
TOMORROW = TIME._calendar(1)
YESTERDAY = TIME._calendar(-1)
SECOND, MINUTE, HOUR = TIME(1), TIME(60), TIME(3600)
