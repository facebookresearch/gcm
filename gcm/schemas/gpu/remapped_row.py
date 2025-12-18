# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class RemappedRowInfo:
    correctable: int
    uncorrectable: int
    pending: int
    failure: int
