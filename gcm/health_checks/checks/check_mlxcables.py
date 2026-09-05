# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check IB cable health via mlxcables DDM diagnostics."""

import glob
import logging
import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple

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

MST_CABLE_GLOB = "/dev/mst/mt*cable_0"


class MlxcablesCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def list_cable_devices(
        self,
        logger: logging.Logger,
    ) -> List[str]:
        """Enumerate MST cable device paths."""
        ...

    def get_cable_ddm(
        self,
        device: str,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Run mlxcables --DDM on a single cable device."""
        ...


@dataclass(frozen=True)
class MlxcablesCheckImpl:
    """Check IB cable DDM diagnostics via mlxcables."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def list_cable_devices(
        self,
        logger: logging.Logger,
    ) -> List[str]:
        """Enumerate MST cable device paths."""
        devices = sorted(glob.glob(MST_CABLE_GLOB))
        logger.info("Found %d cable device(s)", len(devices))
        return devices

    def get_cable_ddm(
        self,
        device: str,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Run mlxcables --DDM on a single cable device."""
        cmd = f"mlxcables -d {device} --DDM"
        logger.info("Running command '%s'", cmd)
        return shell_command(cmd, timeout_secs)


def process_cable_ddm(
    device: str,
    output: str,
    returncode: int,
) -> Tuple[ExitCode, str]:
    """Parse mlxcables DDM output for a single cable."""
    if returncode:
        return ExitCode.WARN, f"{device}: mlxcables failed (rc={returncode})"

    has_alarm = bool(re.search(r"\bALARM\b", output, re.IGNORECASE))
    has_warning = bool(re.search(r"\bWARNING\b", output, re.IGNORECASE))

    issues = []
    if has_alarm:
        issues.append("ALARM")
    if has_warning:
        issues.append("WARNING")

    if issues:
        return ExitCode.WARN, f"{device}: DDM {', '.join(issues)} detected"
    return ExitCode.OK, f"{device}: healthy"


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def check_mlxcables(
    obj: Optional[MlxcablesCheck],
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
    """Check IB cable health via mlxcables DDM diagnostics."""
    if not obj:
        obj = MlxcablesCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_IB_CABLE_DDM,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ib_cable_ddm(),
    ) as rt:
        devices = obj.list_cable_devices(rt.logger)
        if not devices:
            rt.finish(ExitCode.UNKNOWN, "No IB cable devices found")

        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for device in devices:
            try:
                ddm_out = obj.get_cable_ddm(device, timeout, rt.logger)
            except Exception as e:
                ddm_out = handle_subprocess_exception(e)

            exit_code, msg = process_cable_ddm(
                device, ddm_out.stdout, ddm_out.returncode
            )
            overall_msg += msg + "\n"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        rt.finish(overall_exit_code, overall_msg.strip())
