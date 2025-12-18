# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import pathlib
import socket
import sys
from concurrent.futures import as_completed, ThreadPoolExecutor
from contextlib import ExitStack
from shlex import join
from typing import Callable, Collection, Dict, List, Literal, Optional, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.env_variables import EnvCtx
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, ExitCode
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

FnCudaMemTest = Callable[
    [Optional[str], int, int, int, logging.Logger], ShellCommandOut
]


def default_cuda_memtest(
    bin_path: Optional[str],
    device_id: int,
    alloc_size_gb: int,
    timeout: int,
    logger: logging.Logger,
) -> ShellCommandOut:
    """Invoke cudaMemtest binary."""
    """Make sure PATH has a folder that contains cudaMemtest binary."""
    if bin_path is not None:
        cmd_bin = [bin_path]
    else:
        cmd_bin = ["cudaMemTest"]

    cmd = join(
        cmd_bin
        + [
            f"--device={device_id}",
            f"--alloc_mem_gb={alloc_size_gb}",
        ]
    )
    logger.info(f"Running command '{cmd}'")
    result = shell_command(cmd, timeout)
    return result


def run_cuda_memtests_concurrently(
    bin_path: Optional[str],
    device_ids: List[int],
    alloc_size_gb: int,
    timeout: int,
    logger: logging.Logger,
    cuda_memtest: FnCudaMemTest = default_cuda_memtest,
) -> Dict[int, Tuple[ShellCommandOut, ExitCode]]:
    results = {}
    with ThreadPoolExecutor() as executor:
        logger.debug(f"Running cuda memory test in parallel on devices: {device_ids}")
        future_to_device = {
            executor.submit(
                cuda_memtest, bin_path, device_id, alloc_size_gb, timeout, logger
            ): device_id
            for device_id in device_ids
        }

        for future in as_completed(future_to_device):
            device_id = future_to_device[future]
            try:
                result = future.result()
                logger.debug(f"Device {device_id}: {result}")
                exit_code = ExitCode.OK if result.returncode == 0 else ExitCode.CRITICAL
                results[device_id] = (result, exit_code)
            except Exception as e:
                result = handle_subprocess_exception(e)
                logger.error(f"Device {device_id} generated an exception: {e}")
                result.returncode = ExitCode.WARN.value
                results[device_id] = (result, ExitCode.WARN)

    return results


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--size",
    type=int,
    default=4,
    help="Memory allocation size in GB.",
)
@click.option(
    "--memtest-bin",
    type=click.Path(dir_okay=False, path_type=pathlib.Path, exists=True),
    help="Path to the directory with the cudaMemTest binary. If this option is not given it assumes that the binary is in PATH",
)
@click.option(
    "--gpu-devices",
    "-gpu",
    type=click.INT,
    multiple=True,
    help="""The IDs of the GPU devices to test. Can be given multiple IDs.
    If the check is called through prolog or epilog the CUDA_VISIBLE devices will be used to find the allocated devices, otherwise the user should specify the devices to check.
    """,
)
@click.pass_obj
@typechecked
def memtest(
    obj: Optional[FnCudaMemTest],
    cluster: str,
    type: CHECK_TYPE,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    size: int,
    heterogeneous_cluster_v1: bool,
    memtest_bin: Optional[pathlib.Path],
    gpu_devices: Collection[int],
) -> None:
    """Check to make sure a memory block of specified size can be allocated."""
    node: str = socket.gethostname()

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(f"cuda check_memtest: cluster: {cluster}, node: {node}, type: {type}")
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

    run_memtest: FnCudaMemTest = default_cuda_memtest if obj is None else obj
    exit_codes = []
    overall_exit_code = ExitCode.UNKNOWN
    overall_msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.CUDA_MEMTEST.value,
                node=node,
                get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CUDA_MEMTEST,
                lambda: (overall_exit_code, overall_msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_cuda_memtest():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.CUDA_MEMTEST.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)

        devices = []
        if len(gpu_devices):
            devices = list(gpu_devices)
        else:
            if type == "prolog" or type == "epilog":
                devices_env = os.getenv("SLURM_JOB_GPUS") or os.getenv(
                    "CUDA_VISIBLE_DEVICES"
                )

                if not devices_env:
                    devices = []
                else:
                    devices = [int(device) for device in devices_env.split(",")]

        with EnvCtx({"CUDA_VISIBLE_DEVICES": None}):
            exit_code = ExitCode.UNKNOWN
            device_messages = ["Running cuda memory test in parallel."]
            results = run_cuda_memtests_concurrently(
                str(memtest_bin) if memtest_bin else None,
                devices,
                size,
                timeout,
                logger,
                run_memtest,
            )
            logger.debug(f"Cuda memory test results for {len(results)} devices: \n")
            for device_id, full_result in results.items():
                result, exit_code = full_result
                device_msg = ""
                returncode, out, err = result.returncode, result.stdout, result.stderr
                if returncode != 0:
                    device_msg += f"deviceID: {device_id} "
                    if out is not None:
                        device_msg += f"output: {out} "
                    if err is not None:
                        device_msg += f"error: {err} "
                else:
                    device_msg += f"deviceID: {device_id} passed "

                device_messages.append(device_msg)
                exit_codes.append(exit_code)

        overall_exit_code = max(exit_codes or [overall_exit_code])
        if overall_exit_code == ExitCode.UNKNOWN:
            overall_msg += "\nCUDA memory test failed to execute"

        overall_msg += "\n" + "\n".join(device_messages)
        logger.info(f"exit code {overall_exit_code}: {overall_msg}")
        sys.exit(overall_exit_code.value)
