# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import socket
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Collection,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
)

import click

import gni_lib
import psutil
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.device_telemetry_exception_handling import (
    handle_device_telemetry_exception,
)
from gcm.health_checks.device_telemetry_utils import get_gpu_devices
from gcm.health_checks.env_variables import EnvCtx
from gcm.health_checks.measurement_units import convert_bytes
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.device_telemetry_client import (
    DeviceTelemetryClient,
    DeviceTelemetryException,
)
from gcm.monitoring.device_telemetry_nvml import NVMLDeviceTelemetryClient
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.gpu.process import ProcessInfo
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


class NvidiaSmiCli(CheckEnv, Protocol):
    def get_device_telemetry(self) -> DeviceTelemetryClient: ...


@dataclass
class NvidiaSmiCliImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_device_telemetry(self) -> DeviceTelemetryClient:
        return NVMLDeviceTelemetryClient()


def check_gpu_num(
    device_telemetry: DeviceTelemetryClient, expected_gpus: int, logger: logging.Logger
) -> Tuple[ExitCode, str]:
    """Check if the GPUs returned from pynvml query equals the expected number of GPUs"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_gpu_num():
        msg = f"{HealthCheckName.NVIDIA_SMI_GPU_NUM.value} is disabled by killswitch."
        logger.info(msg)

        return ExitCode.OK, msg
    try:
        present_gpus = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    if present_gpus != expected_gpus:
        msg = f"gpu_num check: exit_code: {ExitCode.CRITICAL}, Number of GPUs present, {present_gpus}, is different than expected, {expected_gpus}\n"
        return ExitCode.CRITICAL, msg
    msg = f"gpu_num check: exit_code: {ExitCode.OK}, Number of GPUs present is the same as expected, {expected_gpus}\n"
    return ExitCode.OK, msg


def check_running_procs(
    device_telemetry: DeviceTelemetryClient, type: CHECK_TYPE, logger: logging.Logger
) -> Tuple[ExitCode, str]:
    """Check if other processes are executing on the same GPUs. If no GPU devices are found it return OK.
    This covers the cases that a job was allocated no GPUs, i.e. a CPU only job"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_running_procs():
        msg = f"{HealthCheckName.NVIDIA_SMI_RUNNING_PROCS.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    try:
        devices = get_gpu_devices(device_telemetry, type)
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    if not devices:
        return ExitCode.OK, "running_procs check: No GPU devices were found."

    msg = ""

    # This will restore the environment variable on exit
    with EnvCtx({"CUDA_VISIBLE_DEVICES": None}):
        _, exit_code, msg = attempt_check_running_procs(
            0, devices, msg, device_telemetry
        )

    if exit_code == ExitCode.OK:
        msg = f"running_procs check: No other process is occupying any of the following GPUs: {devices}.\n"

    return exit_code, msg


def attempt_check_running_procs(
    attempt: int, devices: List[int], msg: str, device_telemetry: DeviceTelemetryClient
) -> Tuple[List[ProcessInfo], ExitCode, str]:
    exit_code = ExitCode.OK
    pids = []

    for device in devices:
        try:
            handle = device_telemetry.get_device_by_index(device)
            pids = handle.get_compute_processes()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"running_procs check: GPU {device}: {error_msg}"
        else:
            if pids:
                proc_pids = [p_id.pid for p_id in pids]
                msg += f"running_procs check: attempt #{attempt}: GPU {device} is occupied by {len(pids)} other processes. pids: {proc_pids}\n"

                non_existent_pids = [
                    proc_pid
                    for proc_pid in proc_pids
                    if not psutil.pid_exists(proc_pid)
                ]
                if non_existent_pids:
                    msg += f"running_procs check: attempt #{attempt}: found pids that are non existent but still occupy GPUs {non_existent_pids}\n"
                # if all processes do not exist the check passes as no real process is occupying GPUs
                # else the check indeed fails as there are still zombie processes
                if len(non_existent_pids) < len(pids):
                    exit_code = ExitCode.CRITICAL

    return (pids, exit_code, msg)


def kill_processes(
    pids: List[int],
    attempt: int,
    devices: List[int],
    msg: str,
    device_telemetry: DeviceTelemetryClient,
    timeout: int = 5,
) -> Tuple[bool, str]:
    """
    Kills all processes in 'pids' (SIGKILL on Unix) and waits up to 'timeout'
    seconds for them to exit. Returns True if all processes are gone (or
    already dead), otherwise False.
    """
    procs = [psutil.Process(pid) for pid in pids]
    # Kill each process
    for proc in procs:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            # Already gone
            pass
        except psutil.AccessDenied:
            return (False, msg)

    # Wait for them to terminate (up to 'timeout' seconds)
    gone, alive = psutil.wait_procs(procs, timeout=timeout)
    (_, exit_code, msg) = attempt_check_running_procs(
        attempt, devices, msg, device_telemetry
    )

    # If any are still alive after waiting, return False
    return (len(alive) == 0 and exit_code == ExitCode.OK, msg)


def check_and_kill_running_procs(
    device_telemetry: DeviceTelemetryClient,
    type: CHECK_TYPE,
    retry_count: int,
    retry_interval: int,
    force_kill_process: bool,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check if other processes are executing on the same GPUs. If no GPU devices are found, it returns OK.
    This check will retry for `retry_count` times with a `retry_interval` interval. If there are processes still occupying GPUs, it will force kill the process based on the `force_kill_process` flag."
    This covers the cases that a job was allocated no GPUs, i.e. a CPU only job"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_running_procs_and_kill():
        msg = f"{HealthCheckName.NVIDIA_SMI_RUNNING_PROCS.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    try:
        devices = get_gpu_devices(device_telemetry, type)
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    if not devices:
        return ExitCode.OK, "running_procs check: No GPU devices were found."
    else:
        exit_code = ExitCode.OK
        msg = ""
        pids: List[ProcessInfo] = []

        # This will restore the environment variable on exit
        with EnvCtx({"CUDA_VISIBLE_DEVICES": None}):
            for attempt in range(retry_count):
                (pids, attempt_exit_code, msg) = attempt_check_running_procs(
                    attempt, devices, msg, device_telemetry
                )
                if attempt_exit_code == ExitCode.OK:
                    exit_code = ExitCode.OK if attempt == 0 else ExitCode.WARN
                    break
                elif attempt == retry_count - 1:  # if retry is exhausted
                    exit_code = attempt_exit_code
                else:
                    time.sleep(retry_interval)
        # forcefully cleaning up all running processes if force_kill_process is true
        if force_kill_process and pids:
            proc_pids = [p_id.pid for p_id in pids]
            msg += f"running_procs check: force killed pids: {proc_pids}\n"
            (is_killed, msg) = kill_processes(
                proc_pids, retry_count, devices, msg, device_telemetry
            )
            if is_killed:
                msg += (
                    f"running_procs check: pids are successfully killed: {proc_pids}\n"
                )
                exit_code = ExitCode.OK
            else:
                msg += f"running_procs check: pids are not killed: {proc_pids}\n"
                exit_code = ExitCode.CRITICAL

        if exit_code == ExitCode.OK:
            msg += f"running_procs check: No other process is occupying any of the following GPUs: {devices}.\n"

        return exit_code, msg


def check_app_clock_freq(
    device_telemetry: DeviceTelemetryClient,
    gpu_app_freq: int,
    gpu_app_mem_freq: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check the frequencies of the device"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_clock_freq():
        msg = (
            f"{HealthCheckName.NVIDIA_SMI_CLOCK_FREQ.value} is disabled by killswitch."
        )
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)
    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            clock_info = handle.get_clock_freq()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"clock_freq check: GPU {device}: {error_msg}"
        else:
            if (
                clock_info.graphics_freq < gpu_app_freq
                or clock_info.memory_freq < gpu_app_mem_freq
            ):
                msg += f"clock_freq check: exit_code: {ExitCode.CRITICAL}, GPU {device} has less application freq than expected. Expected: (GPU, GPU_mem) {gpu_app_freq}, {gpu_app_mem_freq} and got {clock_info.graphics_freq}, {clock_info.memory_freq}.\n"
                exit_code = ExitCode.CRITICAL

    if exit_code == ExitCode.OK:
        msg = f"clock_freq check: exit_code: {ExitCode.OK}, Application frequencies are as expected.\n"
    return exit_code, msg


def check_gpu_temp(
    device_telemetry: DeviceTelemetryClient,
    gpu_temperature_threshold: Optional[int],
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check that the temperature of the device is below the specified threshold"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_gpu_temp():
        msg = f"{HealthCheckName.NVIDIA_SMI_GPU_TEMP.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    if gpu_temperature_threshold is None:
        return (
            ExitCode.CRITICAL,
            "gpu_temperature_threshold should not be None",
        )

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)
    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            gpu_temperature = handle.get_temperature()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"gpu_temp check: GPU {device}: {error_msg}"
        else:
            if gpu_temperature > gpu_temperature_threshold:
                exit_code = ExitCode.CRITICAL
                msg += f"gpu_temp check: exit_code: {ExitCode.CRITICAL}, GPU {device} has temperature: {gpu_temperature}, higher than critical threshold of {gpu_temperature_threshold}.\n"

    if exit_code == ExitCode.OK:
        msg = f"gpu_temp check: exit_code: {ExitCode.OK}, all GPU temperatures are lower than max threshold, {gpu_temperature_threshold}.\n"
    return exit_code, msg


def check_mem_usage(
    device_telemetry: DeviceTelemetryClient,
    type: CHECK_TYPE,
    gpu_mem_usage_threshold: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check that the memory usage of the GPU is below the threshold."""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_mem_usage():
        msg = f"{HealthCheckName.NVIDIA_SMI_MEM_USAGE.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    try:
        devices = get_gpu_devices(device_telemetry, type)
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    if not devices:
        return ExitCode.OK, "mem_usage check: No GPU devices were found."
    else:
        exit_code = ExitCode.OK
        msg = ""

        # This will restore the environment variable on exit
        with EnvCtx({"CUDA_VISIBLE_DEVICES": None}):
            for device in devices:
                try:
                    handle = device_telemetry.get_device_by_index(device)
                    memory_info = handle.get_memory_info()
                except DeviceTelemetryException as e:
                    error_code, error_msg = handle_device_telemetry_exception(e)
                    if error_code > exit_code:
                        exit_code = error_code
                    msg += f"mem_usage check: GPU {device}: {error_msg}"
                else:
                    if convert_bytes(memory_info.used, "MiB") > gpu_mem_usage_threshold:
                        msg += f"mem_usage check: GPU {device} mem usage: {convert_bytes(memory_info.used, 'MiB')} is higher than threshold: {gpu_mem_usage_threshold}.\n"
                        exit_code = ExitCode.CRITICAL

        if exit_code == ExitCode.OK:
            msg = f"mem_usage check: all GPUs have mem usage lower than threshold: {gpu_mem_usage_threshold}.\n"

        return exit_code, msg


def get_retired_pages_count(source: Callable[[], Iterable[int]]) -> int:
    return sum(1 for _ in source())


def check_retired_pages(
    device_telemetry: DeviceTelemetryClient,
    gpu_retired_pages_threshold: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check that the retired pages are below the threshold"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_retired_pages():
        msg = f"{HealthCheckName.NVIDIA_SMI_RETIRED_PAGES.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            ret_pages_single_bit = get_retired_pages_count(
                handle.get_retired_pages_multiple_single_bit_ecc_errors
            )
            ret_pages_double_bit = get_retired_pages_count(
                handle.get_retired_pages_double_bit_ecc_error
            )
            pending_ret_pages_status = handle.get_retired_pages_pending_status()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"gpu_retired_pages check: GPU {device}: {error_msg}"
        else:
            if (
                ret_pages_single_bit > gpu_retired_pages_threshold
                or ret_pages_double_bit > gpu_retired_pages_threshold
                or pending_ret_pages_status > 0
            ):
                exit_code = ExitCode.CRITICAL
                msg += f"gpu_retired_pages check: exit_code: {ExitCode.CRITICAL}, GPU {device} has single/double/pending status pages: {ret_pages_single_bit}/{ret_pages_double_bit}/{pending_ret_pages_status}. Retired pages threshold is {gpu_retired_pages_threshold}.\n"

    if exit_code == ExitCode.OK:
        msg = f"gpu_retired_pages check: exit_code: {ExitCode.OK}, all GPUs have pending retired pages and retired pages below the max threshold, {gpu_retired_pages_threshold}.\n"
    return exit_code, msg


def check_ecc_uncorrected_volatile_total(
    device_telemetry: DeviceTelemetryClient,
    ecc_uncorrected_volatile_threshold: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check that the uncorrected ECC errors are below the threshold"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_ecc_uncorrected():
        msg = f"{HealthCheckName.NVIDIA_SMI_ECC_UNCORRECTED.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            ecc_uncorrected = handle.get_ecc_uncorrected_volatile_total()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"ecc_uncorrected_volatile_total check: GPU {device}: {error_msg}"
        else:
            if ecc_uncorrected > ecc_uncorrected_volatile_threshold:
                exit_code = ExitCode.CRITICAL
                msg += f"ecc_uncorrected_volatile_total check: exit_code: {ExitCode.CRITICAL}, GPU {device} has ECC uncorrected: {ecc_uncorrected} above the threshold of {ecc_uncorrected_volatile_threshold}.\n"

    if exit_code == ExitCode.OK:
        msg = f"ecc_uncorrected_volatile_total check: exit_code: {ExitCode.OK}, all GPUs have ECC errors below the threshold of {ecc_uncorrected_volatile_threshold}.\n"

    return exit_code, msg


def check_ecc_corrected_volatile_total(
    device_telemetry: DeviceTelemetryClient,
    ecc_corrected_volatile_threshold: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check that the corrected ECC errors are below the threshold"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_ecc_corrected():
        msg = f"{HealthCheckName.NVIDIA_SMI_ECC_CORRECTED.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            ecc_corrected = handle.get_ecc_corrected_volatile_total()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"ecc_corrected_volatile_total check: GPU {device}: {error_msg}"
        else:
            if ecc_corrected > ecc_corrected_volatile_threshold:
                exit_code = ExitCode.CRITICAL
                msg += f"ecc_corrected_volatile_total check: exit_code: {ExitCode.CRITICAL}, GPU {device} has ECC corrected: {ecc_corrected} above the threshold of {ecc_corrected_volatile_threshold}.\n"

    if exit_code == ExitCode.OK:
        msg = f"ecc_corrected_volatile_total check: exit_code: {ExitCode.OK}, all GPUs have ECC errors below the threshold of {ecc_corrected_volatile_threshold}.\n"

    return exit_code, msg


def check_vbios_mismatch(
    device_telemetry: DeviceTelemetryClient,
    expected_vbios: str,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    """Check that vbios version is consistent across all gpus"""

    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_vbios_mismatch():
        msg = f"{HealthCheckName.NVIDIA_SMI_VBIOS_MISMATCH.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            vbios_version = handle.get_vbios_version()
            if expected_vbios == "":
                expected_vbios = vbios_version
            elif expected_vbios != vbios_version:
                exit_code = ExitCode.CRITICAL
                msg += f"vbios mismatch mismatch: exit_code: {ExitCode.CRITICAL}, Expect '{expected_vbios}' Found '{vbios_version}'\n"

        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"vbios mismatch check: GPU {device}: {error_msg}"

    if exit_code == ExitCode.OK:
        msg = f"vbios mismatch check: exit_code: {ExitCode.OK}, all GPUs have a consistent vbios version.\n"

    return exit_code, msg


def check_row_remap(
    device_telemetry: DeviceTelemetryClient, logger: logging.Logger
) -> Tuple[ExitCode, str]:
    """Check the GPU for remmaped rows"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_row_remap():
        msg = f"{HealthCheckName.NVIDIA_SMI_ROW_REMAP.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            row_remaps = handle.get_remapped_rows()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"row_remap check: GPU {device}: {error_msg}"
        else:
            if row_remaps.pending > 0 or row_remaps.failure > 0:
                exit_code = ExitCode.CRITICAL
                msg += f"row_remap check: exit_code: {ExitCode.CRITICAL}, GPU {device} has pending or failed row remaps: pending/failure/correctable/uncorrectable: {row_remaps.pending}/{row_remaps.failure}/{row_remaps.correctable}/{row_remaps.uncorrectable}.\n"

    if exit_code == ExitCode.OK:
        msg = f"row_remap check: exit_code: {ExitCode.OK}, all GPUs do not have row remap failures or pending remaps.\n"

    return exit_code, msg


def check_row_remap_pending(
    device_telemetry: DeviceTelemetryClient, logger: logging.Logger
) -> Tuple[ExitCode, str]:
    """Check the GPU for remmaped rows that are pending"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_row_remap_pending():
        msg = f"{HealthCheckName.NVIDIA_SMI_ROW_REMAP_PENDING.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            row_remaps = handle.get_remapped_rows()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"row_remap_pending check: GPU {device}: {error_msg}"
        else:
            if row_remaps.pending > 0:
                exit_code = ExitCode.CRITICAL
                msg += f"row_remap_pending check: exit_code: {ExitCode.CRITICAL}, GPU {device} has pending row remaps: pending/failure/correctable/uncorrectable: {row_remaps.pending}/{row_remaps.failure}/{row_remaps.correctable}/{row_remaps.uncorrectable}.\n"

    if exit_code == ExitCode.OK:
        msg = f"row_remap_pending check: exit_code: {ExitCode.OK}, all GPUs do not have pending remaps.\n"

    return exit_code, msg


def check_row_remap_failed(
    device_telemetry: DeviceTelemetryClient, logger: logging.Logger
) -> Tuple[ExitCode, str]:
    """Check the GPU for remmaped rows that failed the remap"""
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_nvidia_smi_row_remap_failed():
        msg = f"{HealthCheckName.NVIDIA_SMI_ROW_REMAP_FAILED.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg

    exit_code = ExitCode.OK
    msg = ""
    try:
        device_count = device_telemetry.get_device_count()
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)

    for device in range(device_count):
        try:
            handle = device_telemetry.get_device_by_index(device)
            row_remaps = handle.get_remapped_rows()
        except DeviceTelemetryException as e:
            error_code, error_msg = handle_device_telemetry_exception(e)
            if error_code > exit_code:
                exit_code = error_code
            msg += f"row_remap_failed check: GPU {device}: {error_msg}"
        else:
            if row_remaps.failure > 0:
                exit_code = ExitCode.CRITICAL
                msg += f"row_remap_failed check: exit_code: {ExitCode.CRITICAL}, GPU {device} has failed row remaps: pending/failure/correctable/uncorrectable: {row_remaps.pending}/{row_remaps.failure}/{row_remaps.correctable}/{row_remaps.uncorrectable}.\n"

    if exit_code == ExitCode.OK:
        msg = f"row_remap_failed check: exit_code: {ExitCode.OK}, all GPUs do not have row remap failures.\n"

    return exit_code, msg


class TemperatureRequiredOption(click.Option):
    def process_value(self, ctx: click.Context, value: Any) -> Any:
        value = super().process_value(ctx, value)

        if value is None and "gpu_temperature" in ctx.params["check"]:
            msg = "gpu_temperature_threshold is required for gpu_temperature check"
            raise click.MissingParameter(ctx=ctx, param=self, message=msg)

        return value


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--check",
    "-c",
    type=click.Choice(
        [
            "gpu_num",
            "running_procs",
            "running_procs_and_kill",
            "clock_freq",
            "gpu_temperature",
            "gpu_mem_usage",
            "gpu_retired_pages",
            "ecc_uncorrected_volatile_total",
            "ecc_corrected_volatile_total",
            "row_remap",
            "row_remap_pending",
            "row_remap_failed",
            "vbios_mismatch",
        ],
    ),
    required=True,
    multiple=True,
    help="Select the checks to perform. Can select more than 1 of the options.",
)
@click.option("--gpu_num", type=click.INT, default=8)
@click.option(
    "--gpu_app_freq",
    type=click.INT,
    default=1155,
    help="Select what the GPU application frequency should be (MHz).",
)
@click.option(
    "--gpu_app_mem_freq",
    type=click.INT,
    default=1593,
    help="Select what the GPU memory application frequency should be (MHz).",
)
@click.option(
    "--gpu_temperature_threshold",
    type=click.INT,
    cls=TemperatureRequiredOption,
    help="""Select the maximum GPU temperature threshold, in Celcius. This is a required parameter if the gpu-temperature check is selected.
    The check fails if temperature exceeds this parameter.""",
)
@click.option(
    "--gpu_mem_usage_threshold",
    type=click.INT,
    default=15,
    help="Select the maximum GPU memory usage threshold MiB. This check fails if the amount of GPU used, in MiB, exceeds this value.",
)
@click.option(
    "--gpu_retired_pages_threshold",
    type=click.INT,
    default=10,  # Max 64 total pages can retire at a time. Using threshold of 10 like RSC here. https://docs.nvidia.com/deploy/dynamic-page-retirement/index.html#faq-pre
    help="Select the maximum number of GPU retired pages. Check fails if retired pages exceed this value.",
)
@click.option(
    "--gpu_vbios",
    type=click.STRING,
    default="",
    help="Select the expected VBIOS. Check fails if GPU VBIOS is different from this value.",
)
@click.option(
    "--ecc_uncorrected_volatile_threshold",
    type=click.INT,
    default=0,  # Same as https://fburl.com/ad2ud3hc
    help="Select the maximum number of uncorrected volatile ECC errors before this check fails.",
)
@click.option(
    "--ecc_corrected_volatile_threshold",
    type=click.INT,
    default=50000000,  # Same as https://fburl.com/0sklg5uu
    help="Select the maximum number of corrected volatile ECC errors before this check fails.",
)
@click.option(
    "--running_procs_retry_count",
    type=click.INT,
    default=3,
    help="Select the number of retries for running process checks before this check fails.",
)
@click.option(
    "--running_procs_interval",
    type=click.INT,
    default=3,
    help="Select how long to wait between running process check retries in seconds.",
)
@click.option(
    "--running_procs_force_kill",
    type=click.BOOL,
    default=False,
    help="Whether the health check should force-kill the running process.",
)
@click.pass_obj
@typechecked
def check_nvidia_smi(
    obj: Optional[NvidiaSmiCli],
    cluster: str,
    type: CHECK_TYPE,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    check: Tuple[str, ...],
    gpu_num: int,
    gpu_app_freq: int,
    gpu_app_mem_freq: int,
    gpu_temperature_threshold: Optional[int],
    gpu_mem_usage_threshold: int,
    gpu_retired_pages_threshold: int,
    gpu_vbios: str,
    ecc_uncorrected_volatile_threshold: int,
    ecc_corrected_volatile_threshold: int,
    running_procs_retry_count: int,
    running_procs_interval: int,
    running_procs_force_kill: bool,
) -> None:
    """Perform nvidia-smi checks to assess the state of the GPUs"""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check_nvidia_smi: check: {check} cluster: {cluster}, node: {node}, type: {type}"
    )
    logger.info(f"{gpu_num=}, {gpu_app_freq=}, {gpu_mem_usage_threshold=}")
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")

    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )

    if obj is None:
        obj = NvidiaSmiCliImpl(cluster, type, log_level, log_folder)

    overall_exit_code = ExitCode.UNKNOWN
    overall_msg = ""

    try:
        device_telemetry = obj.get_device_telemetry()
    except DeviceTelemetryException as e:
        with ExitStack() as s:
            s.enter_context(
                TelemetryContext(
                    sink=sink,
                    sink_opts=sink_opts,
                    logger=logger,
                    cluster=cluster,
                    derived_cluster=derived_cluster,
                    type=type,
                    name=HealthCheckName.NVIDIA_SMI.value,
                    node=node,
                    get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                    gpu_node_id=gpu_node_id,
                )
            )
            s.enter_context(
                OutputContext(
                    type,
                    HealthCheckName.NVIDIA_SMI,
                    lambda: (overall_exit_code, overall_msg),
                    verbose_out,
                )
            )
            overall_exit_code, overall_msg = handle_device_telemetry_exception(e)
            logger.info(
                f"Exception during pynvml init. exit_code: {overall_exit_code} msg: {overall_msg}"
            )
            sys.exit(overall_exit_code.value)

    nvidia_check = [
        (
            "gpu_num",
            HealthCheckName.NVIDIA_SMI_GPU_NUM,
            lambda: check_gpu_num(device_telemetry, gpu_num, logger),
        ),
        (
            "clock_freq",
            HealthCheckName.NVIDIA_SMI_CLOCK_FREQ,
            lambda: check_app_clock_freq(
                device_telemetry, gpu_app_freq, gpu_app_mem_freq, logger
            ),
        ),
        (
            "running_procs",
            HealthCheckName.NVIDIA_SMI_RUNNING_PROCS,
            lambda: check_running_procs(device_telemetry, type, logger),
        ),
        (
            "running_procs_and_kill",
            HealthCheckName.NVIDIA_SMI_RUNNING_PROCS_AND_KILL,
            lambda: check_and_kill_running_procs(
                device_telemetry,
                type,
                running_procs_retry_count,
                running_procs_interval,
                running_procs_force_kill,
                logger,
            ),
        ),
        (
            "gpu_temperature",
            HealthCheckName.NVIDIA_SMI_GPU_TEMP,
            lambda: check_gpu_temp(device_telemetry, gpu_temperature_threshold, logger),
        ),
        (
            "gpu_mem_usage",
            HealthCheckName.NVIDIA_SMI_MEM_USAGE,
            lambda: check_mem_usage(
                device_telemetry, type, gpu_mem_usage_threshold, logger
            ),
        ),
        (
            "gpu_retired_pages",
            HealthCheckName.NVIDIA_SMI_RETIRED_PAGES,
            lambda: check_retired_pages(
                device_telemetry, gpu_retired_pages_threshold, logger
            ),
        ),
        (
            "ecc_uncorrected_volatile_total",
            HealthCheckName.NVIDIA_SMI_ECC_UNCORRECTED,
            lambda: check_ecc_uncorrected_volatile_total(
                device_telemetry, ecc_uncorrected_volatile_threshold, logger
            ),
        ),
        (
            "ecc_corrected_volatile_total",
            HealthCheckName.NVIDIA_SMI_ECC_CORRECTED,
            lambda: check_ecc_corrected_volatile_total(
                device_telemetry, ecc_corrected_volatile_threshold, logger
            ),
        ),
        (
            "vbios_mismatch",
            HealthCheckName.NVIDIA_SMI_VBIOS_MISMATCH,
            lambda: check_vbios_mismatch(device_telemetry, gpu_vbios, logger),
        ),
        (
            "row_remap",
            HealthCheckName.NVIDIA_SMI_ROW_REMAP,
            lambda: check_row_remap(device_telemetry, logger),
        ),
        (
            "row_remap_pending",
            HealthCheckName.NVIDIA_SMI_ROW_REMAP_PENDING,
            lambda: check_row_remap_pending(device_telemetry, logger),
        ),
        (
            "row_remap_failed",
            HealthCheckName.NVIDIA_SMI_ROW_REMAP_FAILED,
            lambda: check_row_remap_failed(device_telemetry, logger),
        ),
    ]

    with OutputContext(
        type,
        HealthCheckName.NVIDIA_SMI,
        lambda: (overall_exit_code, overall_msg),
        verbose_out,
    ):
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_nvidia_smi():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.NVIDIA_SMI.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)

        for check_id, check_name, run_check in nvidia_check:
            if check_id not in check:
                continue
            exit_code = ExitCode.UNKNOWN
            msg = ""
            with TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=check_name.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            ):
                exit_code, msg = run_check()
                overall_msg += msg
                if exit_code > overall_exit_code:
                    overall_exit_code = exit_code

        logger.info(f"Overall exit code {overall_exit_code}\n{overall_msg}")
        sys.exit(overall_exit_code.value)
