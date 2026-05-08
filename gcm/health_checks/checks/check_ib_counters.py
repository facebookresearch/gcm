# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check InfiniBand port error and throughput counters via sysfs.

Reads counters from /sys/class/infiniband/{device}/ports/{port}/counters/
and alerts when error counters exceed configurable thresholds.  This is the
runtime complement to check_iblink: where check_iblink validates link
*presence*, check_ib_counters detects performance-degrading conditions that
silently hurt distributed training (NCCL AllReduce, FSDP, etc.).
"""

import logging
import os
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Optional, Protocol

import click
from gcm.health_checks.check_utils.output_utils import CheckOutput, Metric
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

# Error counters that indicate fabric health problems.
# Any non-zero value is suspicious; rapid increase is critical.
ERROR_COUNTERS: list[str] = [
    "symbol_error",
    "link_error_recovery",
    "link_downed",
    "port_rcv_errors",
    "port_rcv_remote_physical_errors",
    "port_rcv_switch_relay_errors",
    "port_xmit_discards",
    "port_xmit_constraint_errors",
    "port_rcv_constraint_errors",
    "local_link_integrity_errors",
    "excessive_buffer_overrun_errors",
    "VL15_dropped",
]

# Throughput counters (informational, included in metrics output).
THROUGHPUT_COUNTERS: list[str] = [
    "port_xmit_data",
    "port_rcv_data",
    "port_xmit_packets",
    "port_rcv_packets",
]

# Default threshold: total error count above which we alert.
DEFAULT_WARN_THRESHOLD: int = 0
DEFAULT_CRIT_THRESHOLD: int = 100

SYSFS_IB_ROOT = "/sys/class/infiniband"


class IBCountersCheck(CheckEnv, Protocol):
    """Protocol for IB counter reads — enables test injection."""

    def discover_ports(
        self,
        logger: logging.Logger,
    ) -> list[tuple[str, str]]:
        """Return list of (device, port) tuples found on this node."""
        ...

    def read_counter(
        self,
        device: str,
        port: str,
        counter_name: str,
        logger: logging.Logger,
    ) -> Optional[int]:
        """Read a single counter value from sysfs."""
        ...


@dataclass
class IBCountersCheckImpl:
    """Production implementation — reads counters from sysfs."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def discover_ports(
        self,
        logger: logging.Logger,
    ) -> list[tuple[str, str]]:
        """Discover all IB device/port pairs under /sys/class/infiniband."""
        ports: list[tuple[str, str]] = []
        try:
            devices = os.listdir(SYSFS_IB_ROOT)
        except OSError:
            logger.warning("Cannot list %s", SYSFS_IB_ROOT)
            return ports

        for dev in sorted(devices):
            ports_dir = os.path.join(SYSFS_IB_ROOT, dev, "ports")
            try:
                port_nums = os.listdir(ports_dir)
            except OSError:
                logger.warning("Cannot list ports for %s", dev)
                continue
            for p in sorted(port_nums):
                counters_dir = os.path.join(ports_dir, p, "counters")
                if os.path.isdir(counters_dir):
                    ports.append((dev, p))
        return ports

    def read_counter(
        self,
        device: str,
        port: str,
        counter_name: str,
        logger: logging.Logger,
    ) -> Optional[int]:
        """Read a single counter value from sysfs."""
        path = os.path.join(
            SYSFS_IB_ROOT, device, "ports", port, "counters", counter_name
        )
        try:
            with open(path, "r") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            logger.debug(
                "Failed to read counter %s for %s/%s", counter_name, device, port
            )
            return None


@dataclass
class PortCounters:
    """Parsed counters for a single IB port."""

    device: str
    port: str
    errors: dict[str, int] = field(default_factory=dict)
    throughput: dict[str, int] = field(default_factory=dict)


def collect_port_counters(
    obj: IBCountersCheck,
    logger: logging.Logger,
) -> list[PortCounters]:
    """Read all counters for every discovered IB port."""
    results: list[PortCounters] = []
    for device, port in obj.discover_ports(logger):
        pc = PortCounters(device=device, port=port)
        for counter_name in ERROR_COUNTERS:
            val = obj.read_counter(device, port, counter_name, logger)
            if val is not None:
                pc.errors[counter_name] = val
        for counter_name in THROUGHPUT_COUNTERS:
            val = obj.read_counter(device, port, counter_name, logger)
            if val is not None:
                pc.throughput[counter_name] = val
        results.append(pc)
    return results


def process_ib_counters(
    port_counters: list[PortCounters],
    warn_threshold: int,
    crit_threshold: int,
) -> CheckOutput:
    """Evaluate collected counters against thresholds.

    Returns a CheckOutput with per-port error details and Nagios metrics.
    """
    check = CheckOutput("check_ib_counters")

    if not port_counters:
        check.check_status = ExitCode.WARN
        check.short_out = "No IB ports discovered"
        return check

    total_errors = 0
    ports_with_errors = 0
    port_details: list[str] = []
    per_port_metrics: list[list[Metric]] = []

    for pc in port_counters:
        port_label = f"{pc.device}/{pc.port}"
        port_error_total = sum(pc.errors.values())
        total_errors += port_error_total

        if port_error_total > 0:
            ports_with_errors += 1
            nonzero = [f"{name}={val}" for name, val in pc.errors.items() if val > 0]
            port_details.append(f"{port_label}: {'; '.join(nonzero)}")

        port_metrics: list[Metric] = []
        for name, val in pc.errors.items():
            port_metrics.append(
                Metric(
                    name=f"{port_label}.{name}",
                    value=val,
                    metric_warn=str(warn_threshold),
                    metric_crit=str(crit_threshold),
                )
            )
        for name, val in pc.throughput.items():
            port_metrics.append(Metric(name=f"{port_label}.{name}", value=val))
        per_port_metrics.append(port_metrics)

    # Determine overall status.
    if total_errors > crit_threshold:
        check.check_status = ExitCode.CRITICAL
    elif total_errors > warn_threshold:
        check.check_status = ExitCode.WARN
    else:
        check.check_status = ExitCode.OK

    check.short_out = (
        f"{len(port_counters)} ports checked, "
        f"{ports_with_errors} with errors, "
        f"total_errors={total_errors}"
    )
    check.short_metrics = [
        Metric("total_errors", total_errors, metric_warn=str(warn_threshold), metric_crit=str(crit_threshold)),
        Metric("ports_with_errors", ports_with_errors),
        Metric("ports_checked", len(port_counters)),
    ]
    check.long_out = port_details
    check.long_metrics = per_port_metrics
    return check


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--warn-threshold",
    type=click.INT,
    default=DEFAULT_WARN_THRESHOLD,
    show_default=True,
    help="Total error count above which the check returns WARNING.",
)
@click.option(
    "--crit-threshold",
    type=click.INT,
    default=DEFAULT_CRIT_THRESHOLD,
    show_default=True,
    help="Total error count above which the check returns CRITICAL.",
)
@click.pass_obj
@typechecked
def check_ib_counters(
    obj: Optional[IBCountersCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    warn_threshold: int,
    crit_threshold: int,
) -> None:
    """Check IB port error counters against configurable thresholds.

    Reads /sys/class/infiniband/*/ports/*/counters/ for error counters
    (SymbolErrorCounter, LinkDownedCounter, PortRcvErrors, …) and
    throughput counters (PortXmitData, PortRcvData, …).  Alerts when the
    aggregate error count exceeds the configured thresholds.
    """
    if not obj:
        obj = IBCountersCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_IB_COUNTERS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ib_counters(),
    ) as rt:
        try:
            port_counters = collect_port_counters(obj, rt.logger)
        except Exception:
            rt.logger.exception("Failed to collect IB counters")
            port_counters = []

        output = process_ib_counters(port_counters, warn_threshold, crit_threshold)
        rt.finish(output.check_status, str(output))
