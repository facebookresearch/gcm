# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""AMD SMI / ROCm GPU health checks using amd-smi or rocm-smi."""

import logging
import os
import socket
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from typing import (
    Any,
    Collection,
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
from gcm.monitoring.device_telemetry_rocm import ROCmDeviceTelemetryClient
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.gpu.process import ProcessInfo
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

from gcm.health_checks.checks.check_nvidia_smi import (
    attempt_check_running_procs,
    kill_processes,
)


class AmdSmiCli(CheckEnv, Protocol):
    def get_device_telemetry(self) -> DeviceTelemetryClient: ...


@dataclass
class AmdSmiCliImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_device_telemetry(self) -> DeviceTelemetryClient:
        return ROCmDeviceTelemetryClient()


def _check_gpu_num(
    device_telemetry: DeviceTelemetryClient,
    expected_gpus: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_amd_smi_gpu_num():
        msg = f"{HealthCheckName.AMD_SMI_GPU_NUM.value} is disabled by killswitch."
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


def _check_running_procs(
    device_telemetry: DeviceTelemetryClient,
    type: CHECK_TYPE,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_amd_smi_running_procs():
        msg = f"{HealthCheckName.AMD_SMI_RUNNING_PROCS.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg
    try:
        devices = get_gpu_devices(device_telemetry, type)
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)
    if not devices:
        return ExitCode.OK, "running_procs check: No GPU devices were found."
    msg = ""
    with EnvCtx({"ROCR_VISIBLE_DEVICES": None}):
        _, exit_code, msg = attempt_check_running_procs(
            0, devices, msg, device_telemetry
        )
    if exit_code == ExitCode.OK:
        msg = f"running_procs check: No other process is occupying any of the following GPUs: {devices}.\n"
    return exit_code, msg


def _check_and_kill_running_procs(
    device_telemetry: DeviceTelemetryClient,
    type: CHECK_TYPE,
    retry_count: int,
    retry_interval: int,
    force_kill_process: bool,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_amd_smi_running_procs_and_kill():
        msg = f"{HealthCheckName.AMD_SMI_RUNNING_PROCS.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg
    try:
        devices = get_gpu_devices(device_telemetry, type)
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)
    if not devices:
        return ExitCode.OK, "running_procs check: No GPU devices were found."
    exit_code = ExitCode.OK
    msg = ""
    pids: List[ProcessInfo] = []
    with EnvCtx({"ROCR_VISIBLE_DEVICES": None}):
        for attempt in range(retry_count):
            (pids, attempt_exit_code, msg) = attempt_check_running_procs(
                attempt, devices, msg, device_telemetry
            )
            if attempt_exit_code == ExitCode.OK:
                exit_code = ExitCode.OK if attempt == 0 else ExitCode.WARN
                break
            elif attempt == retry_count - 1:
                exit_code = attempt_exit_code
            else:
                time.sleep(retry_interval)
    if force_kill_process and pids:
        proc_pids = [p_id.pid for p_id in pids]
        msg += f"running_procs check: force killed pids: {proc_pids}\n"
        (is_killed, msg) = kill_processes(
            proc_pids, retry_count, devices, msg, device_telemetry
        )
        if is_killed:
            msg += f"running_procs check: pids are successfully killed: {proc_pids}\n"
            exit_code = ExitCode.OK
        else:
            msg += f"running_procs check: pids are not killed: {proc_pids}\n"
            exit_code = ExitCode.CRITICAL
    if exit_code == ExitCode.OK:
        msg += f"running_procs check: No other process is occupying any of the following GPUs: {devices}.\n"
    return exit_code, msg


def _check_app_clock_freq(
    device_telemetry: DeviceTelemetryClient,
    gpu_app_freq: int,
    gpu_app_mem_freq: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_amd_smi_clock_freq():
        msg = f"{HealthCheckName.AMD_SMI_CLOCK_FREQ.value} is disabled by killswitch."
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


def _check_gpu_temp(
    device_telemetry: DeviceTelemetryClient,
    gpu_temperature_threshold: Optional[int],
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_amd_smi_gpu_temp():
        msg = f"{HealthCheckName.AMD_SMI_GPU_TEMP.value} is disabled by killswitch."
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


def _check_mem_usage(
    device_telemetry: DeviceTelemetryClient,
    type: CHECK_TYPE,
    gpu_mem_usage_threshold: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    ff = FeatureValueHealthChecksFeatures()
    if ff.get_healthchecksfeatures_disable_amd_smi_mem_usage():
        msg = f"{HealthCheckName.AMD_SMI_MEM_USAGE.value} is disabled by killswitch."
        logger.info(msg)
        return ExitCode.OK, msg
    try:
        devices = get_gpu_devices(device_telemetry, type)
    except DeviceTelemetryException as e:
        return handle_device_telemetry_exception(e)
    if not devices:
        return ExitCode.OK, "mem_usage check: No GPU devices were found."
    exit_code = ExitCode.OK
    msg = ""
    with EnvCtx({"ROCR_VISIBLE_DEVICES": None}):
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
    default=800,
    help="Select what the GPU application frequency should be (MHz).",
)
@click.option(
    "--gpu_app_mem_freq",
    type=click.INT,
    default=800,
    help="Select what the GPU memory application frequency should be (MHz).",
)
@click.option(
    "--gpu_temperature_threshold",
    type=click.INT,
    cls=TemperatureRequiredOption,
    help="Maximum GPU temperature threshold in Celsius. Required if gpu_temperature check is selected.",
)
@click.option(
    "--gpu_mem_usage_threshold",
    type=click.INT,
    default=15,
    help="Maximum GPU memory usage threshold MiB.",
)
@click.option(
    "--running_procs_retry_count",
    type=click.INT,
    default=3,
    help="Number of retries for running process checks.",
)
@click.option(
    "--running_procs_interval",
    type=click.INT,
    default=3,
    help="Wait between running process check retries in seconds.",
)
@click.option(
    "--running_procs_force_kill",
    type=click.BOOL,
    default=False,
    help="Whether the health check should force-kill the running process.",
)
@click.pass_obj
@typechecked
def check_amd_smi(
    obj: Optional[AmdSmiCli],
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
    running_procs_retry_count: int,
    running_procs_interval: int,
    running_procs_force_kill: bool,
) -> None:
    """Perform AMD SMI / ROCm checks to assess the state of AMD GPUs."""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check_amd_smi: check: {check} cluster: {cluster}, node: {node}, type: {type}"
    )
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
        obj = AmdSmiCliImpl(cluster, type, log_level, log_folder)
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
                    name=HealthCheckName.AMD_SMI.value,
                    node=node,
                    get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                    gpu_node_id=gpu_node_id,
                )
            )
            s.enter_context(
                OutputContext(
                    type,
                    HealthCheckName.AMD_SMI,
                    lambda: (overall_exit_code, overall_msg),
                    verbose_out,
                )
            )
            overall_exit_code, overall_msg = handle_device_telemetry_exception(e)
            logger.info(
                f"Exception during ROCm telemetry init. exit_code: {overall_exit_code} msg: {overall_msg}"
            )
            sys.exit(overall_exit_code.value)
    amd_check = [
        (
            "gpu_num",
            HealthCheckName.AMD_SMI_GPU_NUM,
            lambda: _check_gpu_num(device_telemetry, gpu_num, logger),
        ),
        (
            "clock_freq",
            HealthCheckName.AMD_SMI_CLOCK_FREQ,
            lambda: _check_app_clock_freq(
                device_telemetry, gpu_app_freq, gpu_app_mem_freq, logger
            ),
        ),
        (
            "running_procs",
            HealthCheckName.AMD_SMI_RUNNING_PROCS,
            lambda: _check_running_procs(device_telemetry, type, logger),
        ),
        (
            "running_procs_and_kill",
            HealthCheckName.AMD_SMI_RUNNING_PROCS_AND_KILL,
            lambda: _check_and_kill_running_procs(
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
            HealthCheckName.AMD_SMI_GPU_TEMP,
            lambda: _check_gpu_temp(
                device_telemetry, gpu_temperature_threshold, logger
            ),
        ),
        (
            "gpu_mem_usage",
            HealthCheckName.AMD_SMI_MEM_USAGE,
            lambda: _check_mem_usage(
                device_telemetry, type, gpu_mem_usage_threshold, logger
            ),
        ),
    ]
    with OutputContext(
        type,
        HealthCheckName.AMD_SMI,
        lambda: (overall_exit_code, overall_msg),
        verbose_out,
    ):
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_amd_smi():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.AMD_SMI.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)
        for check_id, check_name, run_check in amd_check:
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
