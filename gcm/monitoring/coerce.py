# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Any, Dict, Optional

from typeguard import typechecked


def non_negative_int(s: str) -> int:
    x = int(s)
    if x < 0:
        raise ValueError("Expected non-negative integer, but got {x}")
    return x


@typechecked
def ensure_dict(x: Any) -> Dict[str, Any]:
    return x


def maybe_int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except ValueError:
        return None


def maybe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except ValueError:
        return None
