# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
from datetime import datetime, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo

import pytest

from gcm.monitoring.clock import (
    AwareDatetime,
    PT,
    time_to_time_aware,
    TimeAwareString,
    tz_aware_fromisoformat,
    unixtime_to_pacific_datetime,
)

try:
    tz_path = os.path.realpath("/etc/localtime", strict=True)
except FileNotFoundError:
    SYSTEM_TZ = ZoneInfo("Etc/UTC")
else:
    SYSTEM_TZ = ZoneInfo(os.path.relpath(tz_path, "/usr/share/zoneinfo"))


@pytest.mark.parametrize(
    "sacct_string, timezone, expected",
    [
        (
            "2023-03-28 14:00:00",
            timezone.utc,
            datetime.fromisoformat("2023-03-28 14:00:00").replace(tzinfo=SYSTEM_TZ),
        ),
        (
            "2023-03-28 14:00:00",
            PT,
            datetime.fromisoformat("2023-03-28 14:00:00-07:00").replace(
                tzinfo=SYSTEM_TZ
            ),
        ),
        (
            "2023-01-28 14:00:00",
            PT,
            datetime.fromisoformat("2023-01-28 14:00:00").astimezone(tz=PT),
        ),
        (
            "2023-03-28 14:00:00",
            None,  # assumes system tz
            datetime.fromisoformat("2023-03-28 14:00:00").astimezone(tz=SYSTEM_TZ),
        ),
        (
            "2023-03-28 14:00:00-07:00",
            None,
            datetime.fromisoformat("2023-03-28 14:00:00-07:00"),
        ),
        (
            "2023-03-28 14:00:00-08:00",
            None,
            datetime.fromisoformat("2023-03-28 14:00:00-08:00"),
        ),
        (
            "2023-03-28 14:00:00+00:00",
            None,
            datetime.fromisoformat("2023-03-28 14:00:00+00:00"),
        ),
        (
            "2023-03-28 14:00:00-07:00",
            PT,
            datetime.fromisoformat("2023-03-28 14:00:00-07:00"),
        ),
        (
            "2023-03-28 14:00:00-07:00",
            timezone.utc,
            datetime.fromisoformat("2023-03-28 14:00:00-07:00"),
        ),
        (
            "2023-03-28 14:00:00+00:00",
            PT,
            datetime.fromisoformat("2023-03-28 14:00:00+00:00"),
        ),
        (
            "2023-03-28 14:00:00+00:00",
            timezone.utc,
            datetime.fromisoformat("2023-03-28 14:00:00+00:00"),
        ),
    ],
)
def test_tz_aware_fromisoformat(
    sacct_string: str, timezone: Optional[tzinfo], expected: AwareDatetime
) -> None:
    actual = tz_aware_fromisoformat(sacct_string, timezone)
    assert actual == expected
    if timezone is not None:
        assert actual.tzinfo == timezone
    else:
        # NOTE: We can't compare to `SYSTEM_TZ` here because the UTC offset for system
        # time may not be fixed (e.g. Pacific/Los_Angeles is -7:00 during daylight
        # savings and -8:00 during standard time) and therefore cannot be compared with
        # a fixed timezone offset. If such a timezone is used, then
        # the result of this test will depend on when the test runs
        assert actual.tzinfo is not None


@pytest.mark.parametrize(
    "unixtime, expected",
    [
        (
            1680037602,
            datetime.fromisoformat("2023-03-28T14:06:42-07:00"),
        ),
        (
            1670020000,
            datetime.fromisoformat("2022-12-02T14:26:40-08:00"),
        ),
    ],
)
def test_unixtime_to_pacific_datetime(unixtime: int, expected: AwareDatetime) -> None:
    actual = unixtime_to_pacific_datetime(unixtime)
    assert actual == expected


@pytest.mark.parametrize(
    "time_string, timezone, expected",
    [
        (
            "2023-03-28 14:00:00",
            None,  # assumes system tz
            datetime.fromisoformat("2023-03-28 14:00:00").astimezone().isoformat(),
        ),
        (
            "2023-03-28 14:00:00-07:00",
            None,
            datetime.fromisoformat("2023-03-28 14:00:00-07:00")
            .astimezone()
            .isoformat(),
        ),
        (
            "2023-03-28 14:00:00-08:00",
            None,
            datetime.fromisoformat("2023-03-28 14:00:00-08:00")
            .astimezone()
            .isoformat(),
        ),
        (
            "2023-03-28 14:00:00+00:00",
            None,
            datetime.fromisoformat("2023-03-28 14:00:00+00:00")
            .astimezone()
            .isoformat(),
        ),
        (
            "2023-03-28 14:00:00",
            timezone.utc,
            datetime.fromisoformat("2023-03-28 14:00:00")
            .astimezone(tz=timezone.utc)
            .isoformat(),
        ),
        (
            "2023-01-28 14:00:00",
            PT,
            datetime.fromisoformat("2023-01-28 14:00:00").astimezone(tz=PT).isoformat(),
        ),
        (
            "2023-01-28 14:00:00+00:00",
            PT,
            "2023-01-28T06:00:00-08:00",
        ),
        (
            "2023-01-28 14:00:00-08:00",
            PT,
            "2023-01-28T14:00:00-08:00",
        ),
        (
            "2023-01-28 06:00:00-08:00",
            timezone.utc,
            "2023-01-28T14:00:00+00:00",
        ),
        (
            "2023-03-28 14:00:00-07:00",
            PT,
            "2023-03-28T14:00:00-07:00",
        ),
        (
            "2023-03-28 07:00:00-07:00",
            timezone.utc,
            "2023-03-28T14:00:00+00:00",
        ),
        (
            "2023-03-28 14:00:00+00:00",
            PT,
            "2023-03-28T07:00:00-07:00",
        ),
        (
            "2023-03-28 14:00:00+00:00",
            timezone.utc,
            "2023-03-28T14:00:00+00:00",
        ),
        (
            "Unknown",
            timezone.utc,
            "Unknown",
        ),
        (
            "Unknown",
            PT,
            "Unknown",
        ),
        (
            "Unknown",
            None,
            "Unknown",
        ),
        (
            "None",
            timezone.utc,
            "None",
        ),
        (
            "None",
            PT,
            "None",
        ),
        (
            "None",
            None,
            "None",
        ),
    ],
)
def test_time_to_time_aware(
    time_string: str, timezone: Optional[tzinfo], expected: TimeAwareString
) -> None:
    actual = time_to_time_aware(time_string, timezone)
    assert actual == expected
