# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from datetime import timedelta, timezone

from gcm.monitoring.clock import PT

PT_TIMEZONE = PT
UTC_TIMEZONE = timezone.utc
PLACEHOLDER_DELTA = timedelta(hours=1)


@dataclass
class FakeClock:
    __current_time: float = field(init=False, default=0.0)
    # 2023-04-28T19:20:03-0700
    __current_unixtime: int = field(init=False, default=1682734803)

    def unixtime(self) -> int:
        return self.__current_unixtime

    def monotonic(self) -> float:
        return self.__current_time

    def sleep(self, duration_sec: float) -> None:
        self.__current_time += max(0.0, duration_sec)
