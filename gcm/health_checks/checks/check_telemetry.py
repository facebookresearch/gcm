# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import sys
from dataclasses import dataclass
from typing import Collection, Optional, Protocol

import click

import gni_lib
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger

from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


class CheckTelemetry(CheckEnv, Protocol):
    def print_telemetry(self) -> None: ...


@dataclass
class CheckTelemetryImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def print_telemetry(self) -> None:
        print("Check telemetry was called")


class ExitCodeParamType(click.ParamType):
    def get_metavar(self, param: click.Parameter) -> str:
        return "[" + ", ".join(str(code.value) for code in ExitCode) + "]"

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> ExitCode:
        try:
            return ExitCode(int(value))
        except ValueError:
            self.fail(f"Invalid exit code: {value}", param, ctx)


class HealthCheckNameParamType(click.ParamType):
    def get_metavar(self, param: click.Parameter) -> str:
        return (
            "[" + ", ".join(enum_member.value for enum_member in HealthCheckName) + "]"
        )

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> HealthCheckName:
        try:
            return HealthCheckName(value)
        except ValueError:
            self.fail(f"Invalid health check name: {value}", param, ctx)


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--exit_code",
    type=ExitCodeParamType(),
    required=True,
    help="The exit code result of the check.[OK=0,WARN=1,CRITICAL=2,UNKNOWN=3]",
)
@click.option(
    "--health-check-name",
    # type=HealthCheckNameParamType(),
    type=click.STRING,
    required=True,
    help="The health-check name.",
)
@click.option(
    "--node",
    type=click.STRING,
    required=True,
    help="The node that the check was executed on.",
)
@click.option(
    "--msg",
    type=click.STRING,
    default="",
    help="The message string to record for telemetry.",
)
@click.option(
    "--job-id",
    type=click.INT,
    default=0,
    help="The job id of the job executing on the node.",
)
@click.pass_obj
@typechecked
def check_telemetry(
    obj: Optional[CheckTelemetry],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    exit_code: ExitCode,
    health_check_name: str,
    node: str,
    msg: str,
    job_id: int,
) -> None:
    """Perform only the telemetry for health-checks"""

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-telemetry: sink: {sink}, cluster: {cluster}, node: {node}, type: {type}, exit_code: {exit_code}, health-check name: {health_check_name}, job id: {job_id}, msg: {msg}."
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
    with TelemetryContext(
        sink=sink,
        sink_opts=sink_opts,
        logger=logger,
        cluster=cluster,
        derived_cluster=derived_cluster,
        type=type,
        name=health_check_name,
        node=node,
        get_exit_code_msg=lambda: (exit_code, msg),
        gpu_node_id=gpu_node_id,
        job_id=job_id,
    ):
        # Exit gracefully to not impact the outcome of the checks
        sys.exit(ExitCode.OK.value)
