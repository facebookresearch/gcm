# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import datetime as dt

import pytest

from gcm.monitoring.date import (
    BoundedClosedInterval,
    ClosedInterval,
    get_datetime,
    get_datetimes,
)


class TestClosedInterval:
    @staticmethod
    def test_throws_on_invalid_bounds() -> None:
        x = dt.datetime(2022, 11, 10, 12, 31, 0)
        with pytest.raises(ValueError):
            ClosedInterval(x, x - dt.timedelta(minutes=5.0))

    @staticmethod
    @pytest.mark.parametrize(
        "interval, x, expected",
        [
            (
                ClosedInterval(
                    dt.datetime(2022, 11, 10, 9, 29, 40),
                    dt.datetime(2022, 11, 10, 10, 1, 11),
                ),
                dt.datetime(2022, 11, 10, 9, 40, 0),
                True,
            ),
            # lower boundary
            (
                ClosedInterval(
                    dt.datetime(2022, 11, 10, 9, 29, 40),
                    dt.datetime(2022, 11, 10, 10, 1, 11),
                ),
                dt.datetime(2022, 11, 10, 9, 29, 40),
                True,
            ),
            # upper boundary
            (
                ClosedInterval(
                    dt.datetime(2022, 11, 10, 9, 29, 40),
                    dt.datetime(2022, 11, 10, 10, 1, 11),
                ),
                dt.datetime(2022, 11, 10, 10, 1, 11),
                True,
            ),
            # less than lower bound
            (
                ClosedInterval(
                    dt.datetime(2022, 11, 10, 9, 29, 40),
                    dt.datetime(2022, 11, 10, 10, 1, 11),
                ),
                dt.datetime(2022, 11, 10, 8, 1, 11),
                False,
            ),
            # greater than upper bound
            (
                ClosedInterval(
                    dt.datetime(2022, 11, 10, 9, 29, 40),
                    dt.datetime(2022, 11, 10, 10, 1, 11),
                ),
                dt.datetime(2022, 11, 10, 12, 1, 11),
                False,
            ),
            # unbounded above
            (
                ClosedInterval(lower=dt.datetime(2022, 11, 10, 9, 29, 40)),
                dt.datetime(2022, 11, 10, 10, 1, 11),
                True,
            ),
            # unbounded above, less than lower bound
            (
                ClosedInterval(lower=dt.datetime(2022, 11, 10, 9, 29, 40)),
                dt.datetime(2022, 11, 9, 10, 1, 11),
                False,
            ),
            # unbounded below
            (
                ClosedInterval(upper=dt.datetime(2022, 11, 10, 10, 1, 11)),
                dt.datetime(2022, 11, 10, 9, 1, 11),
                True,
            ),
            # unbounded below, greater than upper bound
            (
                ClosedInterval(upper=dt.datetime(2022, 11, 10, 10, 1, 11)),
                dt.datetime(2022, 11, 11, 10, 1, 11),
                False,
            ),
            # unbounded
            (ClosedInterval(), dt.datetime.now(), True),
        ],
    )
    def test_contains(interval: ClosedInterval, x: dt.datetime, expected: bool) -> None:
        assert (x in interval) == expected


class TestBoundedClosedInterval:
    @staticmethod
    def test_throws_on_invalid_bounds() -> None:
        x = dt.datetime(2022, 11, 10, 12, 31, 0)
        with pytest.raises(ValueError):
            BoundedClosedInterval(x, x - dt.timedelta(minutes=5.0))


@pytest.mark.parametrize(
    "v, expected",
    [
        (
            "5 pm today",
            dt.datetime.combine(dt.date.today(), dt.time(17, 0, 0)).astimezone(),
        ),
        (
            "nov 11 2022 3:49 pm",
            dt.datetime(2022, 11, 11, 15, 49, 00).astimezone(),
        ),
    ],
)
def test_get_datetime(v: str, expected: dt.datetime) -> None:
    actual = get_datetime(v)
    assert actual == expected
    assert actual.tzinfo is not None


def test_get_datetime_throws() -> None:
    with pytest.raises(ValueError):
        get_datetime("not a date")


def test_get_datetimes() -> None:
    vs = ["5 pm today", "nov 11 2022 3:49 pm"]
    expected = [
        dt.datetime.combine(dt.date.today(), dt.time(17, 0, 0)).astimezone(),
        dt.datetime(2022, 11, 11, 15, 49, 00).astimezone(),
    ]
    expected2 = [get_datetime(v) for v in vs]

    actual = get_datetimes(vs)

    assert actual == expected == expected2
    for t in actual:
        assert t.tzinfo is not None


def test_get_datetimes_throws() -> None:
    vs = ["5 pm today", "not a date"]

    with pytest.raises(ValueError):
        get_datetimes(vs)
