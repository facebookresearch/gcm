# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TYPE_CHECKING


if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass
class Log:
    ts: int
    message: Iterable[DataclassInstance]
