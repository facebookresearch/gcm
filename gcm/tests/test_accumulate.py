# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from itertools import chain
from operator import add, truediv
from typing import Iterable

import pytest

from gcm.monitoring.accumulate import Accumulator
from typeguard import typechecked


class TestAccumulator:
    @staticmethod
    def test_ask_empty() -> None:
        acc = Accumulator(add)

        with pytest.raises(ValueError):
            acc.ask()

        assert acc.ask_maybe() is None

    @staticmethod
    def test_ask_with_initial() -> None:
        acc = Accumulator(add, initial=42)

        actual = acc.ask()

        assert actual == 42

    @staticmethod
    @pytest.mark.parametrize(
        "values, expected",
        [
            ([5, 4], [5, 5]),
            ([4, 5], [4, 5]),
            (range(10), range(10)),
            (chain(range(5), range(4, -1, -1)), chain(range(5), [4] * 5)),
        ],
    )
    @typechecked
    def test_ask_each(values: Iterable[int], expected: Iterable[int]) -> None:
        acc: Accumulator[int] = Accumulator(max)

        actual = []
        for v in values:
            acc.tell(v)
            actual.append(acc.ask())

        assert actual == list(expected)

    @staticmethod
    def test_non_associative() -> None:
        acc: Accumulator[float] = Accumulator(truediv)
        expected = [128.0, 64.0, 32.0, 16.0, 8.0]

        actual = []
        for v in [128.0, 2.0, 2.0, 2.0, 2.0]:
            acc.tell(v)
            actual.append(acc.ask())

        assert len(actual) == len(expected)
        for a, e in zip(actual, expected):
            assert abs(a - e) < 1e-6
