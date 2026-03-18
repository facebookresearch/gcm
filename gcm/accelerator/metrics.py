# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class MetricRequest:
    include_process_info: bool = False


@dataclass(frozen=True)
class MetricSet:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    core_util_pct: float | None = None
    mem_util_pct: float | None = None

    mem_total_bytes: int | None = None
    mem_used_bytes: int | None = None

    temp_c: float | None = None
    power_w: float | None = None
    power_limit_w: float | None = None

    sm_clock_mhz: int | None = None
    mem_clock_mhz: int | None = None

    ecc_corrected: int | None = None
    ecc_uncorrected: int | None = None
