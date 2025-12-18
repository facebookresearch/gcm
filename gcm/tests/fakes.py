# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from subprocess import CompletedProcess
from typing import Iterable, List, Optional

import psutil

from gcm.monitoring.device_telemetry_client import (
    ApplicationClockInfo,
    GPUMemory,
    GPUUtilization,
    ProcessInfo,
    RemappedRowInfo,
)


class FakeGPUDevice:
    def get_compute_processes(self) -> List[ProcessInfo]:
        processes = [(1, 87), (2, 90), (3, 15)]
        return [ProcessInfo(pid, gpu_memory) for pid, gpu_memory in processes]

    def get_retired_pages_double_bit_ecc_error(self) -> Iterable[int]:
        return [1, 4, 6]

    def get_retired_pages_multiple_single_bit_ecc_errors(
        self,
    ) -> Iterable[int]:
        return [3, 4, 8]

    def get_retired_pages_pending_status(self) -> int:
        return 0

    def get_remapped_rows(self) -> RemappedRowInfo:
        return RemappedRowInfo(0, 0, 0, 0)

    def get_ecc_uncorrected_volatile_total(self) -> int:
        return 0

    def get_ecc_corrected_volatile_total(self) -> int:
        return 0

    def get_enforced_power_limit(self) -> Optional[int]:
        return 12

    def get_power_usage(self) -> Optional[int]:
        return 100

    def get_temperature(self) -> int:
        return 42

    def get_memory_info(self) -> GPUMemory:
        return GPUMemory(total=100, free=20, used=80)

    def get_utilization_rates(self) -> GPUUtilization:
        return GPUUtilization(gpu=70, memory=80)

    def get_clock_freq(self) -> ApplicationClockInfo:
        return ApplicationClockInfo(graphics_freq=1155, memory_freq=1593)

    def get_vbios_version(self) -> str:
        return "86.00.4D.00.04"


@dataclass
class FakeClock:
    __current_time: float = field(init=False, default=0.0)
    __current_unixtime: int = field(init=False, default=1668197951)

    def unixtime(self) -> int:
        return self.__current_unixtime

    def monotonic(self) -> float:
        return self.__current_time

    def sleep(self, duration_sec: float) -> None:
        self.__current_time += max(0.0, duration_sec)


@dataclass
class FakeShellCommandOut(CompletedProcess):
    args: List[str] = field(default_factory=list)
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class FakeProcess(psutil.Process):
    _gone: bool = field(init=False, default=False)
    _pid: int = field(init=False, default=8)
    _name: str = field(init=False, default="")
    _pid_reused: int = field(init=False, default=8)

    def __init__(self, pid: int = 8, name: str = ""):
        self._pid = pid
        self._name = name
        self._pid_reused = pid
