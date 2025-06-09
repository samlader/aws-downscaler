"""Time window handling for AWS Downscaler."""

import re
from datetime import datetime, time, timedelta
from typing import List, Optional

import pytz
import structlog
from dateutil import parser

logger = structlog.get_logger()

WEEKDAYS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class TimeWindow:
    """Time window for resource scaling."""

    def __init__(self, spec: str):
        """Initialize time window from spec."""
        self.spec = spec
        self.weekdays: List[int] = []
        self.start_time: Optional[time] = None
        self.end_time: Optional[time] = None
        self.timezone: pytz.BaseTzInfo = pytz.UTC
        self.recurring: bool = True
        self.start_dt: Optional[datetime] = None
        self.end_dt: Optional[datetime] = None

        self._parse_spec()

    def _parse_spec(self) -> None:
        """Parse time window specification."""

        try:
            dt = parser.parse(self.spec)
            if dt.tzinfo is None:
                raise ValueError("Timezone is required for absolute time windows")
            self.recurring = False
            self.start_dt = dt.astimezone(pytz.UTC)
            self.end_dt = self.start_dt.replace(hour=23, minute=59, second=59)
            return
        except (ValueError, TypeError):
            pass

        parts = self.spec.split()
        if len(parts) < 2:
            raise ValueError(f"Invalid time window spec '{self.spec}'")

        weekdays = parts[0].lower()
        if "-" in weekdays:
            start_day, end_day = weekdays.split("-")
            if start_day not in WEEKDAYS or end_day not in WEEKDAYS:
                raise ValueError(f"Invalid weekday range '{weekdays}'")

            start_idx = WEEKDAYS[start_day]
            end_idx = WEEKDAYS[end_day]

            if end_idx < start_idx:
                self.weekdays = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
            else:
                self.weekdays = list(range(start_idx, end_idx + 1))
        else:
            if weekdays not in WEEKDAYS:
                raise ValueError(f"Invalid weekday '{weekdays}'")
            self.weekdays = [WEEKDAYS[weekdays]]

        time_range = parts[1]
        if "-" not in time_range:
            raise ValueError(f"Invalid time range '{time_range}'")

        start_time, end_time = time_range.split("-")
        self.start_time = self._parse_time(start_time)
        self.end_time = self._parse_time(end_time)

        if len(parts) > 2:
            try:
                tz_str = parts[2].strip(",")
                self.timezone = pytz.timezone(tz_str)
            except pytz.exceptions.UnknownTimeZoneError as e:
                raise ValueError(f"Invalid timezone '{parts[2]}': {str(e)}")

    def _parse_time(self, time_str: str) -> time:
        """Parse time string (HH:MM) to time object."""
        try:
            hour, minute = map(int, time_str.split(":"))
            return time(hour, minute)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid time '{time_str}'")

    def is_active(self, now: datetime) -> bool:
        """Check if the time window is active at the given time."""
        if not self.recurring:
            if not self.start_dt or not self.end_dt:
                return False
            return self.start_dt <= now <= self.end_dt

        if not self.start_time or not self.end_time:
            return False

        local_now = now.astimezone(self.timezone)

        if local_now.weekday() not in self.weekdays:
            return False

        start_dt = datetime.combine(local_now.date(), self.start_time)
        end_dt = datetime.combine(local_now.date(), self.end_time)

        start_dt = self.timezone.localize(start_dt)
        end_dt = self.timezone.localize(end_dt)

        if self.end_time < self.start_time:
            end_dt += timedelta(days=1)

            if local_now.time() >= self.start_time:
                return start_dt <= local_now <= end_dt

            if local_now.time() <= self.end_time:
                start_dt -= timedelta(days=1)
                end_dt -= timedelta(days=1)
                return start_dt <= local_now <= end_dt

            return False

        return start_dt <= local_now <= end_dt

    def is_within_grace_period(self, now: datetime, grace_period: int) -> bool:
        """Check if the current time is within the grace period after the window.

        Args:
            now: Current time
            grace_period: Grace period in seconds

        Returns:
            bool: True if within grace period, False otherwise
        """
        if not self.recurring:
            if not self.end_dt:
                return False
            grace_end = self.end_dt + timedelta(seconds=grace_period)
            return now <= grace_end

        if not self.is_active(now) and self.end_time is not None:

            local_now = now.astimezone(self.timezone)

            end_dt = datetime.combine(local_now.date(), self.end_time)
            end_dt = self.timezone.localize(end_dt)

            if self.start_time is not None and self.end_time < self.start_time:
                end_dt += timedelta(days=1)

            grace_end = end_dt + timedelta(seconds=grace_period)
            return local_now <= grace_end and local_now.weekday() in self.weekdays

        return False

    @staticmethod
    def parse_time_specs(specs: Optional[str]) -> List["TimeWindow"]:
        """Parse multiple time window specifications.

        Args:
            specs: String containing one or more time window specs, separated by
                    commas or semicolons.

        Returns:
            List of TimeWindow objects
        """
        if not specs:
            return []

        windows = []

        for spec in re.split("[,;]", specs):
            spec = spec.strip()
            if spec:
                try:
                    windows.append(TimeWindow(spec))
                except ValueError as e:
                    raise ValueError(f"Invalid time window spec '{spec}': {str(e)}")
        return windows

    def __str__(self) -> str:
        """Return string representation of time window."""
        if not self.recurring:
            if self.start_dt is None:
                return "Invalid absolute time window"
            return self.start_dt.isoformat()

        weekdays = []
        for day in self.weekdays:
            for name, idx in WEEKDAYS.items():
                if idx == day and len(name) == 3:
                    weekdays.append(name.capitalize())
                    break

        weekday_str = "-".join(weekdays) if len(weekdays) > 1 else weekdays[0]
        time_str = (
            f"{self.start_time.strftime('%H:%M')}-" f"{self.end_time.strftime('%H:%M')}"
            if self.start_time and self.end_time
            else "00:00-00:00"
        )
        tz_str = str(self.timezone)
        return f"{weekday_str} {time_str} {tz_str}"
