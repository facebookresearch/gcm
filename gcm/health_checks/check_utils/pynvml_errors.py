# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Dict, Tuple

import pynvml
from gcm.health_checks.types import ExitCode

from gcm.monitoring.device_telemetry_client import DeviceTelemetryException

error_exit_codes: Dict[int, Tuple[ExitCode, str]] = {
    pynvml.NVML_ERROR_UNINITIALIZED: (
        ExitCode.WARN,
        "pynvml error: Uinitialized.\n",
    ),
    pynvml.NVML_ERROR_INVALID_ARGUMENT: (
        ExitCode.WARN,
        "pynvml error: Invalid Argument.\n",
    ),
    pynvml.NVML_ERROR_NOT_SUPPORTED: (
        ExitCode.WARN,
        "pynvml error: Not Supported.\n",
    ),
    pynvml.NVML_ERROR_NO_PERMISSION: (
        ExitCode.WARN,
        "pynvml error: Insufficient Permissions.\n",
    ),
    pynvml.NVML_ERROR_ALREADY_INITIALIZED: (
        ExitCode.WARN,
        "pynvml error: Already Initialized.\n",
    ),
    pynvml.NVML_ERROR_NOT_FOUND: (
        ExitCode.WARN,
        "pynvml error: Not Found.\n",
    ),
    pynvml.NVML_ERROR_INSUFFICIENT_SIZE: (
        ExitCode.WARN,
        "pynvml error: Insufficient Size.\n",
    ),
    pynvml.NVML_ERROR_INSUFFICIENT_POWER: (
        ExitCode.WARN,
        "pynvml error: Insufficient External Power.\n",
    ),
    pynvml.NVML_ERROR_DRIVER_NOT_LOADED: (
        ExitCode.WARN,
        "pynvml error: Driver Not Loaded.\n",
    ),
    pynvml.NVML_ERROR_TIMEOUT: (ExitCode.WARN, "Timeout.\n"),
    pynvml.NVML_ERROR_IRQ_ISSUE: (
        ExitCode.WARN,
        "pynvml error: Interrupt Request Issue.\n",
    ),
    pynvml.NVML_ERROR_LIBRARY_NOT_FOUND: (
        ExitCode.WARN,
        "pynvml error: NVML Shared Library Not Found.\n",
    ),
    pynvml.NVML_ERROR_FUNCTION_NOT_FOUND: (
        ExitCode.WARN,
        "pynvml error: Function Not Found.\n",
    ),
    pynvml.NVML_ERROR_CORRUPTED_INFOROM: (
        ExitCode.CRITICAL,
        "pynvml error: Corrupted infoROM.\n",
    ),
    pynvml.NVML_ERROR_GPU_IS_LOST: (ExitCode.CRITICAL, "GPU is lost.\n"),
    pynvml.NVML_ERROR_RESET_REQUIRED: (
        ExitCode.CRITICAL,
        "pynvml error: GPU requires restart.\n",
    ),
    pynvml.NVML_ERROR_OPERATING_SYSTEM: (
        ExitCode.WARN,
        "pynvml error: The operating system has blocked the request.\n",
    ),
    pynvml.NVML_ERROR_LIB_RM_VERSION_MISMATCH: (
        ExitCode.WARN,
        "pynvml error: RM has detected an NVML/RM version mismatch.\n",
    ),
    pynvml.NVML_ERROR_MEMORY: (
        ExitCode.WARN,
        "pynvml error: Insufficient Memory.\n",
    ),
    pynvml.NVML_ERROR_UNKNOWN: (
        ExitCode.WARN,
        "pynvml error: Unknown Error.\n",
    ),
}


def handle_pynvml_error(
    exception: DeviceTelemetryException,
) -> Tuple[ExitCode, str]:
    exc_cause = exception.__cause__
    if (
        exc_cause
        and isinstance(exc_cause, pynvml.NVMLError)
        and exc_cause.value in error_exit_codes
    ):
        return error_exit_codes[exc_cause.value]

    return (
        ExitCode.CRITICAL,
        f"Undocumented error {exception}",
    )
