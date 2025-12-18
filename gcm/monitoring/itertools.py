# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import asdict
from functools import partial
from typing import Callable, Generator, Iterable, List, TypeVar

TItem = TypeVar("TItem")

json_dumps_compact = partial(json.dumps, separators=(",", ":"))
json_dumps_dataclass = lambda data: json.dumps(  # noqa: E731
    asdict(data), separators=(",", ":")
)
json_dumps_dataclass_list = lambda data: json.dumps(  # noqa: E731
    [asdict(d) for d in data], separators=(",", ":")
)


# i.e. "[]"
_OPEN_CLOSE_BRACKET_SIZE = 2


def chunk_by_json_size(
    items: Iterable[TItem], size_hint_bytes: int, json_dump: Callable[[TItem], str]
) -> Generator[List[TItem], None, None]:
    """Minimally chunk (i.e. such that the total number of chunks is minimized)
    an iterable such that the (compact) JSON encoding of each chunk
    is at most size_hint_bytes bytes.

    Raises:
        ValueError: If any item is too large to satisfy the given size hint.
    """
    if size_hint_bytes <= 0:
        raise ValueError(
            f"Size hint must be a positive integer, but got {size_hint_bytes}"
        )

    chunk_size = _OPEN_CLOSE_BRACKET_SIZE
    chunk: List[TItem] = []
    for item in items:
        item_size = len(json_dump(item).encode())
        if item_size + _OPEN_CLOSE_BRACKET_SIZE > size_hint_bytes:
            raise ValueError(
                f"Got item of size {item_size} which is not less than {size_hint_bytes} - {_OPEN_CLOSE_BRACKET_SIZE} bytes"
            )

        # If the current chunk is empty, then the item has no separator. Otherwise, a
        # separator is needed.
        item_size_with_separator = item_size + int(len(chunk) > 0)
        if chunk_size + item_size_with_separator <= size_hint_bytes:
            chunk_size += item_size_with_separator
            chunk.append(item)
            continue

        yield chunk
        chunk_size = item_size + 2
        chunk = [item]

    if chunk:
        yield chunk
