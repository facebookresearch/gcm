# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Any, List, Type

import pytest

from gcm.monitoring.itertools import chunk_by_json_size, json_dumps_compact


@pytest.mark.parametrize(
    "items, size_hint_bytes, expected",
    [
        ([], 10, []),
        (["foo", "bar", "baz"], 12, [["foo"], ["bar"], ["baz"]]),
        (["foo", "bar", "baz"], 13, [["foo", "bar"], ["baz"]]),
        ([{"foo": "bar"}, "baz", "quux"], 15, [[{"foo": "bar"}], ["baz", "quux"]]),
    ],
)
def test_chunk_by_json_size(
    items: List[Any], size_hint_bytes: int, expected: List[List[Any]]
) -> None:
    actual = list(chunk_by_json_size(items, size_hint_bytes, json_dumps_compact))

    assert actual == expected
    for chunk in actual:
        assert len(json_dumps_compact(chunk).encode()) <= size_hint_bytes


@pytest.mark.parametrize(
    "items, size_hint_bytes, expected_exc, expected_chunks_before_exc",
    [
        (["foo"], 2, ValueError, []),
        (["foo", "bar", "baz", {"foo": "bar"}], 13, ValueError, [["foo", "bar"]]),
    ],
)
def test_chunk_by_json_size_throws(
    items: List[Any],
    size_hint_bytes: int,
    expected_exc: Type[BaseException],
    expected_chunks_before_exc: List[List[Any]],
) -> None:
    chunks = []
    with pytest.raises(expected_exc):
        for chunk in chunk_by_json_size(items, size_hint_bytes, json_dumps_compact):
            chunks.append(chunk)

    assert chunks == expected_chunks_before_exc
