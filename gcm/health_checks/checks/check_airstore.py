# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Collection, List, Optional, Protocol, Tuple

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


@click.group()
def check_airstore() -> None:
    """
    AIRStore-based application readiness checks
    """


class AirstoreCheck(CheckEnv, Protocol):
    def get_credential_count(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...


@dataclass
class AirstoreCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_credential_count(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return piped_shell_command(
            [
                "ls /var/airstore/cred",
                "grep -c bulk",
            ],
            timeout_secs,
        )


def process_flash_array_credential_count(
    output: str,
    error_codes: List[int],
    expected_count_ge: int,
) -> Tuple[ExitCode, str]:
    if sum(error_codes) > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"FAILED to execute, error_codes: {error_codes}, output: {output}",
        )
    actual_count = int(output)
    return (
        ExitCode.CRITICAL if actual_count < expected_count_ge else ExitCode.OK,
        f"actual_count: {actual_count}, expected_count_ge: {expected_count_ge}",
    )


@check_airstore.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--expected-count-ge",
    type=click.INT,
    required=True,
    help="Expected number of configured Flash Array credentials >= value",
)
@click.pass_obj
@typechecked
def flash_array_credential_count(
    obj: Optional[AirstoreCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    expected_count_ge: int,
) -> None:
    """
    Ensure that machines have Flash Array credentials properly configured
    """

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-airstore flash-array-credential-count: cluster: {cluster}, node: {node}, type: {type}, expected-count-ge: {expected_count_ge}"
    )
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")
    if obj is None:
        obj = AirstoreCheckImpl(cluster, type, log_level, log_folder)

    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )

    exit_code = ExitCode.UNKNOWN
    msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.AIRSTORE_CREDENTIAL_COUNT.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.AIRSTORE_CREDENTIAL_COUNT,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_airstore_credential_count():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.AIRSTORE_CREDENTIAL_COUNT.value} is disabled by killswitch"
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            proc_out: PipedShellCommandOut = obj.get_credential_count(timeout, logger)
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            proc_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_flash_array_credential_count(
            proc_out.stdout,
            proc_out.returncode,
            expected_count_ge,
        )
        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)
