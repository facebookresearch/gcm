# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import time
import zoneinfo
from datetime import datetime, timezone, tzinfo
from typing import NewType, Optional, Protocol

# SAFETY: https://github.com/pganssle/zoneinfo/issues/125
PT = zoneinfo.ZoneInfo("America/Los_Angeles")  # type: ignore[abstract]

# datetimes where tzinfo is not None
AwareDatetime = NewType("AwareDatetime", datetime)
TimeAwareString = NewType("TimeAwareString", str)


class Clock(Protocol):
    """An object that can tell and pass time."""

    def unixtime(self) -> int:
        """Get the current unixtime."""

    def monotonic(self) -> float:
        """Get the current time. The absolute time need not be meaningful. Only relative
        times are well-defined so that the difference between calls represents the
        amount of time that passed, in seconds, e.g.

        >>> clock: Clock = ...
        >>> start = clock.monotonic()
        >>> end = clock.monotonic()
        >>> end - start  # elapsed time in seconds

        Invariants:
        1. The sequence obtained from successive calls must be monotonically increasing
        """

    def sleep(self, duration_sec: float) -> None:
        """Block until the given duration has passed."""


class ClockImpl:
    def unixtime(self) -> int:
        return int(time.time())

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, duration_sec: float) -> None:
        time.sleep(duration_sec)


def unixtime_to_pacific_datetime(ts: int) -> AwareDatetime:
    """Return unixtime as pacific datetime."""
    ds = datetime.fromtimestamp(ts, tz=timezone.utc)
    pt_ds = ds.astimezone(PT)
    return AwareDatetime(pt_ds)


def tz_aware_fromisoformat(
    sacct_string: str, system_tz: Optional[tzinfo] = None
) -> AwareDatetime:
    """Given an ISO-8601 string `s`, return a timezone aware `datetime.datetime` with the given timezone `tz`.

    First, we attach timezone information if needed to produce a timezone aware datetime `d`.
    If `s` is naive (i.e. has no UTC offset), then it is interpreted as the system time.
    Otherwise, `s` unambiguously refers to a single point in time.

    Then, `d` is converted to the target timezone `d_` such that
    1. `d == d_` and
    2. `d_.tzinfo == tz`
    """
    ds = datetime.fromisoformat(sacct_string).astimezone(tz=system_tz)
    return AwareDatetime(ds)


def time_to_time_aware(
    time: str, system_tz: Optional[tzinfo] = None
) -> TimeAwareString:
    """Receives an ISO-8601 tz aware or unaware string and returns an ISO-8601 tz aware string."""
    if time in ["Unknown", "None", "N/A"]:
        return TimeAwareString(time)
    return TimeAwareString(tz_aware_fromisoformat(time, system_tz).isoformat())
