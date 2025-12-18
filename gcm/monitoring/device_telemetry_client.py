#!/usr/bin/env python
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
# -*- coding: utf-8 -*-
from typing import Iterable, List, Optional, Protocol, runtime_checkable

from gcm.schemas.gpu.application_clock import ApplicationClockInfo
from gcm.schemas.gpu.memory import GPUMemory
from gcm.schemas.gpu.process import ProcessInfo
from gcm.schemas.gpu.remapped_row import RemappedRowInfo
from gcm.schemas.gpu.utilization import GPUUtilization


class DeviceTelemetryException(Exception):
    """
    Base exception type for device telemetry exceptions
    that can be handled by the caller.
    """


class GPUDevice(Protocol):
    """Class that holds and gets GPU Information"""

    def get_compute_processes(self) -> List[ProcessInfo]: ...

    def get_retired_pages_double_bit_ecc_error(self) -> Iterable[int]: ...

    def get_retired_pages_multiple_single_bit_ecc_errors(
        self,
    ) -> Iterable[int]: ...

    def get_retired_pages_pending_status(self) -> int:
        """Checks if any pages are pending retirement and need a reboot to fully retire"""
        ...

    def get_remapped_rows(self) -> RemappedRowInfo: ...

    def get_ecc_uncorrected_volatile_total(self) -> int: ...

    def get_ecc_corrected_volatile_total(self) -> int: ...

    def get_enforced_power_limit(self) -> Optional[int]: ...

    def get_power_usage(self) -> Optional[int]: ...

    def get_temperature(self) -> int: ...

    def get_memory_info(self) -> GPUMemory: ...

    def get_utilization_rates(self) -> GPUUtilization: ...

    def get_clock_freq(self) -> ApplicationClockInfo: ...

    def get_vbios_version(self) -> str: ...


@runtime_checkable
class DeviceTelemetryClient(Protocol):
    def get_device_count(self) -> int: ...

    def get_device_by_index(self, index: int) -> GPUDevice: ...
