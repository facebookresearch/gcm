# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Literal


def convert_bytes(bytes: int, convert_to: Literal["KiB", "MiB", "GiB", "TiB"]) -> float:
    """Convert bytes to the selected unit of measure, KiB, MiB, GiB, or TiB."""
    conversion_power = {
        "KiB": 1,
        "MiB": 2,
        "GiB": 3,
        "TiB": 4,
    }
    if convert_to not in conversion_power:
        raise KeyError(
            f"Conversion unit {convert_to} is not one of KiB, MiB, GiB, or TiB."
        )

    return bytes / (1024 ** conversion_power[convert_to])
