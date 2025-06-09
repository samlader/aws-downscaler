"""Tests for the schedule module."""

from datetime import datetime

import pytest
import pytz
from freezegun import freeze_time

from aws_downscaler.schedule import TimeWindow


def test_parse_recurring_time_spec():
    """Test parsing recurring time specifications."""
    spec = "Mon-Fri 09:00-17:00 America/New_York"
    window = TimeWindow(spec)

    assert window.recurring
    assert window.weekdays == [0, 1, 2, 3, 4]
    assert window.start_time.hour == 9
    assert window.start_time.minute == 0
    assert window.end_time.hour == 17
    assert window.end_time.minute == 0
    assert window.timezone == pytz.timezone("America/New_York")


def test_parse_absolute_time_spec():
    """Test parsing absolute time specifications."""
    spec = "2024-04-01T08:00:00-04:00"
    window = TimeWindow(spec)

    assert not window.recurring
    assert window.start_dt.year == 2024
    assert window.start_dt.month == 4
    assert window.start_dt.day == 1
    assert window.start_dt.hour == 12
    assert window.start_dt.minute == 0
    assert window.start_dt.tzinfo == pytz.UTC

    assert window.end_dt.year == 2024
    assert window.end_dt.month == 4
    assert window.end_dt.day == 1
    assert window.end_dt.hour == 23
    assert window.end_dt.minute == 59


def test_invalid_recurring_spec():
    """Test handling of invalid recurring time specifications."""
    with pytest.raises(ValueError):
        TimeWindow("Invalid 09:00-17:00 UTC")

    with pytest.raises(ValueError):
        TimeWindow("Mon-Fri Invalid UTC")

    with pytest.raises(ValueError):
        TimeWindow("Mon-Fri 09:00-17:00 Invalid")


def test_invalid_absolute_spec():
    """Test handling of invalid absolute time specifications."""
    with pytest.raises(ValueError):
        TimeWindow("2024-13-01T08:00:00-04:00")

    with pytest.raises(ValueError):
        TimeWindow("2024-04-01T25:00:00-04:00")

    with pytest.raises(ValueError):
        TimeWindow("2024-04-01T08:00:00")


@freeze_time("2024-04-01 14:30:00 UTC")
def test_recurring_window_active():
    """Test checking if recurring time window is active."""

    window = TimeWindow("Mon-Fri 09:00-17:00 America/New_York")
    now = datetime.now(pytz.UTC)

    assert window.is_active(now)

    with freeze_time("2024-04-01 03:00:00 UTC"):
        now = datetime.now(pytz.UTC)
        assert not window.is_active(now)

    with freeze_time("2024-04-06 14:30:00 UTC"):
        now = datetime.now(pytz.UTC)
        assert not window.is_active(now)


@freeze_time("2024-04-01 14:30:00 UTC")
def test_absolute_window_active():
    """Test checking if absolute time window is active."""
    now = datetime.now(pytz.UTC)

    window = TimeWindow("2024-04-01T00:00:00-04:00")
    assert window.is_active(now)

    window = TimeWindow("2024-04-02T00:00:00-04:00")
    assert not window.is_active(now)


def test_parse_multiple_specs():
    """Test parsing multiple time specifications."""
    specs = "Mon-Fri 09:00-17:00 America/New_York, 2024-04-01T00:00:00-04:00"
    windows = TimeWindow.parse_time_specs(specs)

    assert len(windows) == 2
    assert windows[0].recurring
    assert not windows[1].recurring

    assert TimeWindow.parse_time_specs(None) == []
    assert TimeWindow.parse_time_specs("") == []


def test_parse_recurring_time_window():
    """Test parsing recurring time window specification."""
    window = TimeWindow("Mon-Fri 09:00-17:00 UTC")
    assert window.recurring
    assert window.weekdays == [0, 1, 2, 3, 4]
    assert window.start_time.hour == 9
    assert window.start_time.minute == 0
    assert window.end_time.hour == 17
    assert window.end_time.minute == 0
    assert window.timezone == pytz.UTC


def test_parse_absolute_time_window():
    """Test parsing absolute time window specification."""
    window = TimeWindow("2024-03-16T12:00:00Z")
    assert not window.recurring
    assert window.start_dt.year == 2024
    assert window.start_dt.month == 3
    assert window.start_dt.day == 16
    assert window.start_dt.hour == 12
    assert window.start_dt.minute == 0
    assert window.start_dt.tzinfo == pytz.UTC
    assert window.end_dt.hour == 23
    assert window.end_dt.minute == 59


def test_invalid_recurring_time_window():
    """Test invalid recurring time window specification."""
    with pytest.raises(ValueError):
        TimeWindow("Invalid 09:00-17:00 UTC")

    with pytest.raises(ValueError):
        TimeWindow("Mon-Fri 0900-1700 UTC")

    with pytest.raises(ValueError):
        TimeWindow("Mon-Fri 09:00-17:00 INVALID")


def test_invalid_absolute_time_window():
    """Test invalid absolute time window specification."""
    with pytest.raises(ValueError):
        TimeWindow("2024-03-16")

    with pytest.raises(ValueError):
        TimeWindow("invalid-date")


def test_recurring_window_is_active():
    """Test checking if recurring time window is active."""
    window = TimeWindow("Mon-Fri 09:00-17:00 UTC")

    dt = datetime(2024, 3, 13, 10, 0, tzinfo=pytz.UTC)
    assert window.is_active(dt)

    dt = datetime(2024, 3, 13, 18, 0, tzinfo=pytz.UTC)
    assert not window.is_active(dt)

    dt = datetime(2024, 3, 16, 12, 0, tzinfo=pytz.UTC)
    assert not window.is_active(dt)


def test_absolute_window_is_active():
    """Test checking if absolute time window is active."""
    window = TimeWindow("2024-03-16T12:00:00Z")

    dt = datetime(2024, 3, 16, 12, 0, tzinfo=pytz.UTC)
    assert window.is_active(dt)

    dt = datetime(2024, 3, 16, 15, 0, tzinfo=pytz.UTC)
    assert window.is_active(dt)

    dt = datetime(2024, 3, 17, 12, 0, tzinfo=pytz.UTC)
    assert not window.is_active(dt)


def test_parse_multiple_time_specs():
    """Test parsing multiple time specifications."""
    specs = "Mon-Fri 09:00-17:00 UTC, Sat 10:00-14:00 UTC"
    windows = TimeWindow.parse_time_specs(specs)

    assert len(windows) == 2
    assert windows[0].weekdays == [0, 1, 2, 3, 4]
    assert windows[1].weekdays == [5]


def test_timezone_handling():
    """Test handling different timezones."""

    window = TimeWindow("Mon-Fri 09:00-17:00 America/New_York")

    dt = datetime(2024, 3, 13, 19, 0, tzinfo=pytz.UTC)
    assert window.is_active(dt)

    dt = datetime(2024, 3, 14, 1, 0, tzinfo=pytz.UTC)
    assert not window.is_active(dt)
