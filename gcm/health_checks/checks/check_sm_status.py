# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check IB Subnet Manager reachability via sminfo."""

import logging
import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


class SmStatusCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def get_sm_info(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Run sminfo to query the Subnet Manager."""
        ...


@dataclass(frozen=True)
class SmStatusCheckImpl:
    """Check IB Subnet Manager reachability."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_sm_info(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Run sminfo to query the Subnet Manager."""
        cmd = "sminfo"
        logger.info("Running command '%s'", cmd)
        return shell_command(cmd, timeout_secs)


def process_sm_info(
    output: str,
    returncode: int,
) -> Tuple[ExitCode, str]:
    """Parse sminfo output for SM state."""
    if returncode:
        return ExitCode.CRITICAL, f"SM unreachable (sminfo rc={returncode}): {output}"

    # sminfo output format: "sminfo: sm lid X lmc Y guid 0x... prio N state M MASTER"
    state_match = re.search(r"\bstate\s+\d+\s+(\S+)", output)
    if not state_match:
        return ExitCode.WARN, f"Could not parse SM state from: {output}"

    state = state_match.group(1).upper()
    if "MASTER" in state:
        return ExitCode.OK, f"SM reachable, state {state}"

    return ExitCode.WARN, f"SM reachable but in state {state} (expected MASTER)"


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def check_sm_status(
    obj: Optional[SmStatusCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
) -> None:
    """Check IB Subnet Manager reachability via sminfo."""
    if not obj:
        obj = SmStatusCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.IB_SM_STATUS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_ib_sm_status(),
    ) as rt:
        try:
            sm_out = obj.get_sm_info(timeout, rt.logger)
        except Exception as e:
            sm_out = handle_subprocess_exception(e)

        exit_code, msg = process_sm_info(sm_out.stdout, sm_out.returncode)
        rt.finish(exit_code, msg)
