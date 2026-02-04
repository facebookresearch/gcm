# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
import os
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from typing import (
    Collection,
    get_args,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    piped_shell_command,
    PipedShellCommandOut,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

"""
NVIDIA Data Center GPU Manager (DCGM) diagnostics.
Example output of the dcgmi diag -r 4 command:
akokolis@fairwus3-1-htc-727:~$ dcgmi diag -r 4
Successfully ran diagnostic for group.
+---------------------------+------------------------------------------------+
| Diagnostic                | Result                                         |
+===========================+================================================+
|-----  Deployment  --------+------------------------------------------------|
| Blacklist                 | Pass                                           |
| NVML Library              | Pass                                           |
| CUDA Main Library         | Pass                                           |
| Permissions and OS Blocks | Pass                                           |
| Persistence Mode          | Pass                                           |
| Environment Variables     | Pass                                           |
| Page Retirement/Row Remap | Pass                                           |
| Graphics Processes        | Pass                                           |
| Inforom                   | Pass                                           |
+-----  Integration  -------+------------------------------------------------+
| PCIe                      | Pass - All                                     |
+-----  Hardware  ----------+------------------------------------------------+
| GPU Memory                | Pass - All                                     |
| Diagnostic                | Pass - All                                     |
| Pulse Test                | Pass - All                                     |
+-----  Stress  ------------+------------------------------------------------+
| SM Stress                 | Pass - All                                     |
| Targeted Stress           | Pass - All                                     |
| Targeted Power            | Pass - All                                     |
| Memory Bandwidth          | Pass - All                                     |
| Memtest                   | Pass - All                                     |
+---------------------------+------------------------------------------------+

This command is not uniform across clusters. Let the user decide if all the Deployment
categories need to be tested for a pass.

The categories can also change. Repo: https://github.com/NVIDIA/DCGM/blob/main/dcgmi/Diag.cpp

Example of dcgmi nvlink -e -g 0 command (showing only 1 link here):
akokolis@sandbox-htc-1:~/test_prolog$ dcgmi nvlink -e -g 0 | head -n 9
+-----------------------------+------------------------------------------------+
| NVLINK Error Counts                                                          |
| GPU 0                                                                        |
+=============================+================================================+
| Link 0                      |                                                |
| -> CRC FLIT Error           | 0                                              |
| -> CRC Data Error           | 0                                              |
| -> Replay Error             | 0                                              |
| -> Recovery Error           | 0                                              |


Example of dcgmi nvlink -s command:
+----------------------+
|  NvLink Link Status  |
+----------------------+
GPUs:
    gpuId 0:
        U U U U U U U U U U U U
    gpuId 1:
        U U U U U U U U U U U U
    gpuId 2:
        U U U U U U U U U U U U
    gpuId 3:
        U U U U U U U U U U U U
    gpuId 4:
        U U U U U U U U U U U U
    gpuId 5:
        U U U U U U U U U U U U
    gpuId 6:
        U U U U U U U U U U U U
    gpuId 7:
        U U U U U U U U U U U U
NvSwitches:
    No NvSwitches found.

Key: Up=U, Down=D, Disabled=X, Not Supported=_
"""

DEPLOYMENT_CATEGORIES = Literal[
    # Deployment
    "Blacklist",
    "NVML Library",
    "CUDA Main Library",
    "Permissions and OS Blocks",
    "Persistence Mode",
    "Environment Variables",
    "Page Retirement/Row Remap",
    "Graphics Processes",
    "Inforom",
    # Integration
    "PCIe",
    # Hardware
    "GPU Memory",
    "Diagnostic",
    "Pulse Test",
    # Stress
    "SM Stress",
    "Targeted Stress",
    "Targeted Power",
    "Memory Bandwidth",
    "Memtest",
]

# Errors that not necessarily constitute a failed execution
NON_FATAL_ERRORS = [205]


class DCGM(CheckEnv, Protocol):
    def get_diagnostics(
        self, level: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_nvlink_error_report(
        self, gpu_index: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_nvlink_status_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...


@dataclass
class DCGMImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str
    host: str = "localhost"

    def get_diagnostics(
        self, level: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = f"dcgmi diag --host {self.host} -j -r {level}"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def get_nvlink_error_report(
        self, gpu_index: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = f"dcgmi nvlink --host {self.host} -j -e -g {gpu_index}"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def get_nvlink_status_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        cmd = [f"dcgmi nvlink --host {self.host} -s", "grep -i -A1 gpuId"]
        logger.info("Running command: dcgmi nvlink -s | grep -i -A1 gpuId`")
        return piped_shell_command(cmd, timeout_secs)


def _get_test_status(test: dict) -> str:
    """Get the overall status from a test result.

    DCGM 4.x uses test_summary.status for aggregated results.
    DCGM 3.x uses results[0].status.
    """
    if "test_summary" in test and "status" in test["test_summary"]:
        return test["test_summary"]["status"]
    # Fallback for DCGM 3.x format
    if test.get("results") and len(test["results"]) > 0:
        return test["results"][0].get("status", "")
    return ""


def process_dcgmi_diag_output(
    output: str, error_code: int, exclude_category: List[str]
) -> Tuple[ExitCode, str]:
    if error_code > 0 and error_code not in NON_FATAL_ERRORS:
        return (
            ExitCode.WARN,
            f"dcgmi diag command FAILED to execute. error_code: {error_code} output: {output}.\n",
        )
    if len(output) == 0:
        return ExitCode.WARN, "dcgmi diag FAILED to execute.\n"

    output_dict = json.loads(output)
    # DCGM 3.x uses "DCGM GPU Diagnostic", DCGM 4.x uses "DCGM Diagnostic"
    diag_key = None
    for key in ["DCGM GPU Diagnostic", "DCGM Diagnostic"]:
        if key in output_dict:
            diag_key = key
            break

    if (
        len(output_dict) == 0
        or diag_key is None
        or "test_categories" not in output_dict[diag_key]
    ):
        return ExitCode.WARN, "dcgmi diag FAILED to execute.\n"

    msg: str = ""
    exit_code: ExitCode = ExitCode.OK

    for category in output_dict[diag_key]["test_categories"]:
        for test in category["tests"]:
            if test["name"] in exclude_category:
                continue

            status = _get_test_status(test)
            if status == "Fail":
                msg += f"{test['name']} failed.\n"
                exit_code = ExitCode.CRITICAL
            elif status == "Warn":
                msg += f"{test['name']} warning.\n"
                if exit_code < ExitCode.WARN:
                    exit_code = ExitCode.WARN

    if exit_code == ExitCode.OK:
        msg = "All checks passed.\n"

    return exit_code, msg


def process_dcgmi_nvlink_error_output(
    output: str,
    error_code: int,
    data_error_thr: int,
    flit_error_thr: int,
    replay_error_thr: int,
    recovery_error_thr: int,
) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"dcgmi nvlink -e command FAILED to execute. error_code: {error_code} output: {output}.\n",
        )
    if len(output) == 0:
        return (
            ExitCode.WARN,
            "dcgmi nvlink -e command FAILED to execute.\n",
        )

    output_dict = json.loads(output)
    if len(output_dict) == 0 or "body" not in output_dict:
        return (
            ExitCode.WARN,
            "dcgmi nvlink -e command FAILED to execute.\n",
        )

    msg: str = ""
    exit_code: ExitCode = ExitCode.OK
    for link_name, values in output_dict["body"].items():
        for name, sub_value in values["children"].items():
            value = sub_value["value"]
            if (
                "Not Supported" in value
                or "Not Specified" in value
                or not value.isdigit()
            ):
                # idk what is going on here. seems transient.
                continue

            if "CRC Data Error" in name and data_error_thr < int(value):
                exit_code = ExitCode.CRITICAL
                msg += f"High CRC Data Error count detected link: {link_name}, error count: {value}.\n"

            elif "CRC FLIT Error" in name and flit_error_thr < int(value):
                exit_code = ExitCode.CRITICAL
                msg += f"High CRC FLIT Error count detected link: {link_name}, error count: {value}.\n"

            elif "Recovery Error" in name and recovery_error_thr < int(value):
                exit_code = ExitCode.CRITICAL
                msg += f"High Recovery Error count detected link: {link_name}, error count: {value}.\n"

            elif "Replay Error" in name and replay_error_thr < int(value):
                exit_code = ExitCode.CRITICAL
                msg += f"High Replay Error count detected link: {link_name}, error count: {value}.\n"

    if exit_code == ExitCode.OK:
        msg = "All nvlink error checks passed.\n"

    return exit_code, msg


def process_nvlink_status_output(output: str, error_code: int) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"dcgmi nvlink -s command FAILED to execute. error_code: {error_code} output: {output}.\n",
        )
    if len(output) == 0:
        return (
            ExitCode.WARN,
            "dcgmi nvlink -s command FAILED to execute.\n",
        )
    msg: str = ""
    exit_code: ExitCode = ExitCode.OK
    gpu_id = ""
    for line in output.split("\n"):
        if "gpuId" in line:
            gpu_id = line.strip()
            continue
        down_links = line.count("D")
        disabled_links = line.count("X")
        if down_links > 0 or disabled_links > 0:
            exit_code = ExitCode.CRITICAL
            msg += f"{gpu_id} has {down_links} links down and {disabled_links} links disabled.\n"

    if exit_code == ExitCode.OK:
        msg = "All nvlink links are up for all GPUs.\n"

    return exit_code, msg


@click.group()
def check_dcgmi() -> None:
    """dcgmi based commands. i.e. diag, nvlink"""


@check_dcgmi.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--exclude_category",
    "-x",
    multiple=True,
    type=click.Choice(get_args(DEPLOYMENT_CATEGORIES)),
    default=[],
)
@click.option("--diag_level", type=click.IntRange(1, 4), default=1)
@click.option(
    "--host",
    type=str,
    default="localhost",
    help="endpoint to connect to dcgm on",
)
@click.pass_obj
@typechecked
def diag(
    obj: Optional[DCGM],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    exclude_category: Sequence[DEPLOYMENT_CATEGORIES],
    diag_level: int,
    host: str,
) -> None:
    """Check the GPUs with the dcgmi diag -r <level> command"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check_dcgmi diag: cluster: {cluster}, node: {node}, type: {type}, exclude_category: {exclude_category}, host: {host}"
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

    exit_code = ExitCode.UNKNOWN
    msg = ""
    if obj is None:
        obj = DCGMImpl(cluster, type, log_level, log_folder, host)

    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.DCGMI_DIAG.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.DCGMI_DIAG, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_dcgmi_diag():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.DCGMI_DIAG.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            diag_output: ShellCommandOut = obj.get_diagnostics(
                diag_level, timeout, logger
            )
        except Exception as e:
            diag_output = handle_subprocess_exception(e)

        exit_code, msg = process_dcgmi_diag_output(
            diag_output.stdout,
            diag_output.returncode,
            list(exclude_category),
        )
        logger.info(f"exit code {exit_code}: {msg}")
        sys.exit(exit_code.value)


@check_dcgmi.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--check",
    "-c",
    type=click.Choice(
        [
            "nvlink_errors",
            "nvlink_status",
        ],
    ),
    required=True,
    multiple=True,
    help="Select the nvlink checks to perform. Can select more than 1 of the options.",
)
@click.option("--gpu_num", "-g", type=click.INT, default=8, help="Number of GPUs")
@click.option(
    "--data_error_threshold",
    type=click.INT,
    default=0,
    help="Number of data errors for check to fail",
)
@click.option(
    "--flit_error_threshold",
    type=click.INT,
    default=0,
    help="Number of flit errors for check to fail",
)
@click.option(
    "--recovery_error_threshold",
    type=click.INT,
    default=0,
    help="Number of recovery errors for check to fail",
)
@click.option(
    "--replay_error_threshold",
    type=click.INT,
    default=0,
    help="Number of replay errors for check to fail",
)
@click.option(
    "--host",
    type=str,
    default="localhost",
    help="endpoint to connect to dcgm on",
)
@click.pass_obj
@typechecked
def nvlink(
    obj: Optional[DCGM],
    cluster: str,
    type: CHECK_TYPE,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    check: Tuple[str, ...],
    gpu_num: int,
    data_error_threshold: int,
    flit_error_threshold: int,
    recovery_error_threshold: int,
    replay_error_threshold: int,
    host: str,
) -> None:
    """Check the GPU links with the nvlink command"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check_dcgmi nvlink: cluster: {cluster}, node: {node}, type: {type}, gpu_num: {gpu_num},\
 Data/Flit/Recovery/Replay error thresholds: {data_error_threshold}, {flit_error_threshold}, {recovery_error_threshold}, {replay_error_threshold}, host: {host}"
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
        obj = DCGMImpl(cluster, type, log_level, log_folder, host)

    overall_exit_code = ExitCode.UNKNOWN
    overall_msg = ""
    with OutputContext(
        type,
        HealthCheckName.DCGMI_NVLINK,
        lambda: (overall_exit_code, overall_msg),
        verbose_out,
    ):
        if "nvlink_errors" in check:
            exit_code = ExitCode.UNKNOWN
            msg = ""
            with TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.DCGMI_NVMLINK_ERROR.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            ):
                ff = FeatureValueHealthChecksFeatures()
                if ff.get_healthchecksfeatures_disable_dcgmi_nvlink_error():
                    exit_code = ExitCode.OK
                    msg = f"{HealthCheckName.DCGMI_NVMLINK_ERROR.value} is disabled by killswitch."
                    overall_exit_code = exit_code
                    overall_msg = msg
                    logger.info(msg)
                    sys.exit(exit_code.value)
                for gpu in range(gpu_num):
                    try:
                        nvlink_output: ShellCommandOut = obj.get_nvlink_error_report(
                            gpu, timeout, logger
                        )
                    except Exception as e:
                        nvlink_output = handle_subprocess_exception(e)
                    try:
                        exit_code, msg = process_dcgmi_nvlink_error_output(
                            nvlink_output.stdout,
                            nvlink_output.returncode,
                            data_error_threshold,
                            flit_error_threshold,
                            replay_error_threshold,
                            recovery_error_threshold,
                        )
                    except Exception as e:
                        exit_code = ExitCode.WARN
                        msg = f"Exception while parsing nvlink error: {e}"
                    overall_msg += f"GPU: {gpu}: {msg}"
                    if exit_code > overall_exit_code:
                        overall_exit_code = exit_code

        if "nvlink_status" in check:
            exit_code = ExitCode.UNKNOWN
            msg = ""
            with TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.DCGMI_NVMLINK_STATUS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            ):
                ff = FeatureValueHealthChecksFeatures()
                if ff.get_healthchecksfeatures_disable_dcgmi_nvlink_status():
                    exit_code = ExitCode.OK
                    msg = f"{HealthCheckName.DCGMI_NVMLINK_STATUS.value} is disabled by killswitch."
                    overall_exit_code = exit_code
                    overall_msg = msg
                    logger.info(msg)
                    sys.exit(exit_code.value)
                try:
                    nvlink_status_output: PipedShellCommandOut = (
                        obj.get_nvlink_status_report(timeout, logger)
                    )
                except Exception as e:
                    exc_out = handle_subprocess_exception(e)
                    nvlink_status_output = PipedShellCommandOut(
                        [exc_out.returncode], exc_out.stdout
                    )

                exit_code, msg = process_nvlink_status_output(
                    nvlink_status_output.stdout,
                    nvlink_status_output.returncode[0],
                )
                overall_msg += msg
                if exit_code > overall_exit_code:
                    overall_exit_code = exit_code

        logger.info(f"exit code {overall_exit_code}\n{overall_msg}")
        sys.exit(overall_exit_code.value)
