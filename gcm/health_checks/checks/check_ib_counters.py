# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Read IB port counters from sysfs and alert on errors."""

import logging
import os
from collections.abc import Collection
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

SYSFS_IB_BASE = "/sys/class/infiniband"

ERROR_COUNTERS = [
    "symbol_error",
    "link_error_recovery",
    "link_downed",
    "port_rcv_errors",
    "port_rcv_constraint_errors",
    "port_xmit_discards",
    "excessive_buffer_overrun_errors",
    "local_link_integrity_errors",
]

CRITICAL_COUNTERS = {"link_downed"}


class IbCountersCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def get_ib_counters(
        self,
        logger: logging.Logger,
    ) -> str:
        """Read IB port counters from sysfs and return as structured text."""
        ...


@dataclass(frozen=True)
class IbCountersCheckImpl:
    """Read IB port counters from sysfs."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_ib_counters(
        self,
        logger: logging.Logger,
    ) -> str:
        """Read all IB port error counters from sysfs."""
        lines: List[str] = []
        if not os.path.isdir(SYSFS_IB_BASE):
            return "ERROR: no IB devices found"

        for device in sorted(os.listdir(SYSFS_IB_BASE)):
            ports_dir = os.path.join(SYSFS_IB_BASE, device, "ports")
            if not os.path.isdir(ports_dir):
                continue
            for port in sorted(os.listdir(ports_dir)):
                counters_dir = os.path.join(ports_dir, port, "counters")
                if not os.path.isdir(counters_dir):
                    continue
                for counter_name in ERROR_COUNTERS:
                    counter_path = os.path.join(counters_dir, counter_name)
                    try:
                        with open(counter_path) as f:
                            value = f.read().strip()
                    except OSError:
                        value = "N/A"
                    lines.append(f"{device}/{port}/{counter_name}={value}")

        return "\n".join(lines) if lines else "ERROR: no IB counters found"


def process_ib_counters(
    output: str,
    threshold: int,
) -> Tuple[ExitCode, str]:
    """Parse sysfs counter output and determine exit code."""
    if output.startswith("ERROR:"):
        return ExitCode.WARN, output

    errors: List[str] = []
    has_critical = False

    for line in output.strip().split("\n"):
        if "=" not in line:
            continue
        path, value_str = line.rsplit("=", 1)
        if value_str == "N/A":
            continue
        try:
            value = int(value_str)
        except ValueError:
            continue

        if value > threshold:
            counter_name = path.rsplit("/", 1)[-1]
            errors.append(f"{path}={value}")
            if counter_name in CRITICAL_COUNTERS:
                has_critical = True

    if not errors:
        return ExitCode.OK, "All IB port counters within threshold."

    msg = f"{len(errors)} counter(s) above threshold: " + "; ".join(errors)
    return ExitCode.CRITICAL if has_critical else ExitCode.WARN, msg


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--error-threshold",
    type=click.INT,
    default=0,
    help="Counter value threshold. Values above this trigger an alert.",
)
@click.pass_obj
@typechecked
def check_ib_counters(
    obj: Optional[IbCountersCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    error_threshold: int,
) -> None:
    """Check IB port error counters from sysfs."""
    if not obj:
        obj = IbCountersCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.IB_PORT_COUNTERS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_ib_port_counters(),
    ) as rt:
        counters_output = obj.get_ib_counters(rt.logger)
        rt.logger.info(f"IB counters output:\n{counters_output}")
        exit_code, msg = process_ib_counters(counters_output, error_threshold)
        rt.finish(exit_code, msg)
