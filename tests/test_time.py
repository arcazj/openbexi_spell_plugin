"""Independent UTC/calendar oracles for the native TIME package."""
from contextvars import copy_context
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from openbexi_spell import HOUR, MINUTE, NOW, SECOND, TIME, TODAY, TOMORROW, YESTERDAY
from openbexi_spell.time import _clock, _format


@pytest.fixture(autouse=True)
def utc_clock():
    clock = _clock.set(lambda: datetime(2024, 2, 29, 23, 59, 59, 123456, tzinfo=timezone.utc))
    formatting = _format.set("%d-%b-%Y %H:%M:%S")
    yield
    _clock.reset(clock)
    _format.reset(formatting)


@pytest.mark.parametrize("date", ["29-Feb-2024", "2024-02-29", "29/02/2024", "2024/02/29"])
@pytest.mark.parametrize("suffix,hour,minute,second", [("", 0, 0, 0), (" 12:34", 12, 34, 0),
    (" 12:34:56", 12, 34, 56), (":12:34", 12, 34, 0), (":12:34:56", 12, 34, 56)])
def test_documented_absolute_input_formats(date, suffix, hour, minute, second):
    result = TIME(date + suffix)
    expected = datetime(2024, 2, 29, hour, minute, second, tzinfo=timezone.utc)
    assert result.value() == expected
    assert result.abs() == expected.timestamp()
    assert result.rel() is None
    assert result.isAbs() and not result.isRel()


@pytest.mark.parametrize("source,seconds", [("+23.500", 23.5), ("-23.500", -23.5),
    ("+001 23:10", 169800), ("-001 23:10:30", -169830), ("+00:00:30", 30),
    ("-00:00:00.000001", -0.000001), ("+100:00:00", 360000), ("+0", 0)])
def test_relative_inputs_and_round_trip(source, seconds):
    result = TIME(source)
    assert result.isRel() and result.rel() == seconds
    assert TIME(str(result)).value() == result.value()
    assert result.abs() == (NOW.value() + timedelta(seconds=seconds)).timestamp()


def test_reference_example_29_independent_timestamp_and_fields():
    result = TIME("2006/04/02 20:32:34")
    assert result.abs() == 1144009954.0  # PDF's 1144002754 is two hours off UTC.
    assert (result.julianDay(), result.year(), result.month(), result.day(), result.hour(),
            result.minute(), result.second()) == (92, 2006, 4, 2, 20, 32, 34)
    TIME.fmt("%Y/%m/%d %H:%M:%S")
    assert str(result) == "2006/04/02 20:32:34"


def test_dynamic_calendar_constants_and_frozen_copy_cross_midnight():
    dynamic = NOW
    frozen = TIME(NOW)
    first = NOW.value()
    _clock.set(lambda: first + timedelta(seconds=2))
    assert dynamic.value() == first + timedelta(seconds=2)
    assert frozen.value() == first
    assert TODAY.value() == datetime(2024, 3, 1, tzinfo=timezone.utc)
    assert TOMORROW.value() == datetime(2024, 3, 2, tzinfo=timezone.utc)
    assert YESTERDAY.value() == datetime(2024, 2, 29, tzinfo=timezone.utc)


def test_clock_and_format_are_isolated_between_procedures():
    previous = str(NOW)
    def another():
        _clock.set(lambda: datetime(2030, 1, 1, tzinfo=timezone.utc))
        TIME.fmt("%Y")
        return str(NOW)
    assert copy_context().run(another) == "2030"
    assert str(NOW) == previous


def test_relative_absolute_arithmetic_negative_and_subsecond():
    origin = TIME("2024-02-29")
    assert (origin + 24 * HOUR).value() == datetime(2024, 3, 1, tzinfo=timezone.utc)
    assert (origin - TIME("2024-03-01")).rel() == -86400
    assert (3 * HOUR + 20 * SECOND - MINUTE).rel() == 10760
    assert (TIME(Decimal("0.000001")) * -3).rel() == -0.000003
    assert (60 - MINUTE).rel() == 0
    assert (MINUTE + origin).value() == origin.value() + timedelta(minutes=1)


def test_precision_epoch_timezone_and_output_are_deterministic():
    result = TIME("2024-02-29T12:34:56.123456Z")
    assert result.millisecond() == 123 and result.microsecond() == 123456
    TIME.fmt("%Y-%m-%d %H:%M:%S.%f %j %% %b")
    assert str(result) == "2024-02-29 12:34:56.123456 060 % Feb"
    assert TIME.epoch(-0.000001).value() == datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert TIME(datetime(2024, 3, 1, tzinfo=timezone(timedelta(hours=3)))).value() == datetime(2024, 2, 29, 21, tzinfo=timezone.utc)


@pytest.mark.parametrize("source", ["", " +1", "+1 ", "2023-02-29", "31-Apr-2024", "01-Xxx-2024",
    "2024-02-29 24:00", "+00:60", "+00:00:60", "+001 24:00", "+nan", "2024-02-29 junk",
    "+1.0000001", "2024-02-29 12:34:56.1234567", "2001-01-01%", "0000-01-01"])
def test_invalid_time_boundaries(source):
    with pytest.raises(ValueError):
        TIME(source)


@pytest.mark.parametrize("value", [True, None, [], {}, datetime(2024, 1, 1)])
def test_invalid_time_types(value):
    with pytest.raises((TypeError, ValueError)):
        TIME(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 1e100, Decimal("0.0000001")])
def test_nonfinite_out_of_range_or_excess_precision(value):
    with pytest.raises(ValueError):
        TIME(value)


@pytest.mark.parametrize("format", ["%", "%Q", "%s", "", None, 12])
def test_output_format_validation(format):
    if format is None:
        assert TIME.fmt() == "%d-%b-%Y %H:%M:%S"
    else:
        with pytest.raises(ValueError):
            TIME.fmt(format)


def test_type_safe_arithmetic_comparison_and_calendar_errors():
    absolute = TIME("2024-01-01")
    with pytest.raises(TypeError):
        absolute + absolute
    with pytest.raises(TypeError):
        SECOND - absolute
    with pytest.raises(TypeError):
        absolute * 2
    with pytest.raises(TypeError):
        SECOND * True
    with pytest.raises(TypeError):
        SECOND.year()
    with pytest.raises(TypeError):
        SECOND < absolute
    assert SECOND < MINUTE and SECOND != MINUTE and SECOND == TIME("+1")
    assert absolute != "2024-01-01"
    assert TIME("2024-12-31").julianDay() == 366
    _clock.set(lambda: datetime(2024, 1, 1))
    with pytest.raises(ValueError):
        NOW.value()


@pytest.mark.parametrize("date", ["2023-01-01", "2024-01-01", "2021-01-01", "2024-12-31"])
def test_portable_datetime_directives_and_week_year_boundaries(date):
    value = TIME(date)
    TIME.fmt("%a %A %b %B %c %I %p %U %W %w %x %X %y %z %Z %G %u %V")
    expected = value.value().strftime(TIME.fmt())
    assert str(value) == expected
