# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Callable, Iterable, List, Optional, TypeVar

import pynvml

from gcm.monitoring.device_telemetry_client import (
    ApplicationClockInfo,
    DeviceTelemetryException,
    GPUMemory,
    GPUUtilization,
    ProcessInfo,
    RemappedRowInfo,
)
from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R")


def pynvml_exception_handler(func: Callable[P, R]) -> Callable[P, R]:
    def inner_function(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except pynvml.NVMLError as e:
            raise DeviceTelemetryException from e

    return inner_function


class NVMLGPUDevice:
    def __init__(self, handle: pynvml.c_nvmlDevice_t):
        self.handle = handle

    @pynvml_exception_handler
    def get_compute_processes(self) -> List[ProcessInfo]:
        processes = pynvml.nvmlDeviceGetComputeRunningProcesses(self.handle)
        return [
            ProcessInfo(process.pid, process.usedGpuMemory) for process in processes
        ]

    @pynvml_exception_handler
    def get_retired_pages_double_bit_ecc_error(self) -> Iterable[int]:
        return pynvml.nvmlDeviceGetRetiredPages(
            self.handle,
            pynvml.NVML_PAGE_RETIREMENT_CAUSE_DOUBLE_BIT_ECC_ERROR,
        )

    @pynvml_exception_handler
    def get_retired_pages_multiple_single_bit_ecc_errors(
        self,
    ) -> Iterable[int]:
        return pynvml.nvmlDeviceGetRetiredPages(
            self.handle,
            pynvml.NVML_PAGE_RETIREMENT_CAUSE_MULTIPLE_SINGLE_BIT_ECC_ERRORS,
        )

    @pynvml_exception_handler
    def get_retired_pages_pending_status(self) -> int:
        return pynvml.nvmlDeviceGetRetiredPagesPendingStatus(self.handle)

    @pynvml_exception_handler
    def get_remapped_rows(self) -> RemappedRowInfo:
        remapped_rows = pynvml.nvmlDeviceGetRemappedRows(self.handle)
        return RemappedRowInfo(
            remapped_rows[0],
            remapped_rows[1],
            remapped_rows[2],
            remapped_rows[3],
        )

    @pynvml_exception_handler
    def get_ecc_uncorrected_volatile_total(self) -> int:
        return pynvml.nvmlDeviceGetTotalEccErrors(
            self.handle,
            pynvml.NVML_MEMORY_ERROR_TYPE_UNCORRECTED,
            pynvml.NVML_VOLATILE_ECC,
        )

    @pynvml_exception_handler
    def get_ecc_corrected_volatile_total(self) -> int:
        return pynvml.nvmlDeviceGetTotalEccErrors(
            self.handle,
            pynvml.NVML_MEMORY_ERROR_TYPE_CORRECTED,
            pynvml.NVML_VOLATILE_ECC,
        )

    @pynvml_exception_handler
    def get_enforced_power_limit(self) -> Optional[int]:
        return pynvml.nvmlDeviceGetEnforcedPowerLimit(self.handle)

    @pynvml_exception_handler
    def get_power_usage(self) -> Optional[int]:
        return pynvml.nvmlDeviceGetPowerUsage(self.handle)

    @pynvml_exception_handler
    def get_temperature(self) -> int:
        return pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)

    @pynvml_exception_handler
    def get_memory_info(self) -> GPUMemory:
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
        return GPUMemory(memory_info.total, memory_info.free, memory_info.used)

    @pynvml_exception_handler
    def get_utilization_rates(self) -> GPUUtilization:
        utilization_info = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
        return GPUUtilization(utilization_info.gpu, utilization_info.memory)

    @pynvml_exception_handler
    def get_vbios_version(self) -> str:
        return pynvml.nvmlDeviceGetVbiosVersion(self.handle)

    @pynvml_exception_handler
    def get_clock_freq(self) -> ApplicationClockInfo:
        # For the type parameter https://github.com/gpuopenanalytics/pynvml/blob/41e1657948b18008d302f5cb8af06539adc7c792/pynvml/nvml.py#L168
        NVML_CLOCK_GRAPHICS = 0
        NVML_CLOCK_MEM = 2

        graphics_freq = pynvml.nvmlDeviceGetApplicationsClock(
            self.handle, NVML_CLOCK_GRAPHICS
        )
        memory_freq = pynvml.nvmlDeviceGetApplicationsClock(self.handle, NVML_CLOCK_MEM)
        return ApplicationClockInfo(graphics_freq, memory_freq)


class NVMLDeviceTelemetryClient:
    @pynvml_exception_handler
    def __init__(self) -> None:
        pynvml.nvmlInit()

    @pynvml_exception_handler
    def get_device_count(self) -> int:
        return pynvml.nvmlDeviceGetCount()

    @pynvml_exception_handler
    def get_device_by_index(self, index: int) -> NVMLGPUDevice:
        device = pynvml.nvmlDeviceGetHandleByIndex(index)
        return NVMLGPUDevice(device)
