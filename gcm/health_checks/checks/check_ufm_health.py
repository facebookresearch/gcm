# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check UFM for unhealthy IB ports.

This is a cluster-wide check designed to run from a UFM management
node.  It reads the UFM unhealthy-ports dump file and reports any
ports that UFM has flagged as unhealthy.
"""

import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

DEFAULT_UNHEALTHY_PORTS_FILE = "/opt/ufm/log/opensm-unhealthy-ports.dump"


class UfmHealthCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def read_unhealthy_ports(self, logger: logging.Logger) -> str:
        """Read the UFM unhealthy-ports dump file."""
        ...

    def truncate_unhealthy_ports(self, logger: logging.Logger) -> None:
        """Truncate the dump file after reading to avoid stale alerts."""
        ...


@dataclass(frozen=True)
class UfmHealthCheckImpl:
    """Read UFM unhealthy-ports dump file."""

    cluster: str
    type: str
    log_level: str
    log_folder: str
    unhealthy_ports_file: str = DEFAULT_UNHEALTHY_PORTS_FILE

    def read_unhealthy_ports(self, logger: logging.Logger) -> str:
        """Read the UFM unhealthy-ports dump file."""
        logger.info("Reading UFM unhealthy ports file: %s", self.unhealthy_ports_file)
        try:
            with open(self.unhealthy_ports_file) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def truncate_unhealthy_ports(self, logger: logging.Logger) -> None:
        """Truncate the dump file after reading to avoid stale alerts."""
        try:
            with open(self.unhealthy_ports_file, "w"):
                pass
            logger.info("Truncated %s", self.unhealthy_ports_file)
        except OSError as e:
            logger.warning("Failed to truncate %s: %s", self.unhealthy_ports_file, e)


def process_unhealthy_ports(content: str) -> Tuple[ExitCode, str]:
    """Parse OpenSM unhealthy-ports dump content.

    Expected format (CSV with header comment):
      # NodeGUID, PortNum, NodeDesc, PeerNodeGUID, PeerPortNum, PeerNodeDesc, {Conditions}, TimeStamp
      0x..., 25, "switch01", 0x..., 25, "switch02", {FLAPPING}, Fri Mar 20 01:13:40 2026
    """
    stripped = content.strip()
    if not stripped:
        return ExitCode.OK, "No unhealthy ports reported by UFM."

    # Filter out comment lines
    data_lines = [
        line
        for line in stripped.split("\n")
        if line.strip() and not line.startswith("#")
    ]

    if not data_lines:
        return ExitCode.OK, "No unhealthy ports reported by UFM."

    port_count = len(data_lines)
    preview = "\n".join(data_lines[:20])
    if port_count > 20:
        preview += f"\n... ({port_count - 20} more)"

    return (
        ExitCode.CRITICAL,
        f"{port_count} unhealthy port(s) reported by UFM:\n{preview}",
    )


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--unhealthy-ports-file",
    type=click.Path(),
    default=DEFAULT_UNHEALTHY_PORTS_FILE,
    help="Path to UFM unhealthy-ports dump file.",
)
@click.option(
    "--truncate/--no-truncate",
    default=False,
    help="Truncate the dump file after reading to avoid stale alerts.",
)
@click.pass_obj
@typechecked
def check_ufm_health(
    obj: Optional[UfmHealthCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    unhealthy_ports_file: str,
    truncate: bool,
) -> None:
    """Check UFM for unhealthy IB ports.

    Run from a UFM management node.
    """
    if not obj:
        obj = UfmHealthCheckImpl(
            cluster, type, log_level, log_folder, unhealthy_ports_file
        )

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_IB_UFM_HEALTH,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ib_ufm_health(),
    ) as rt:
        content = obj.read_unhealthy_ports(rt.logger)
        exit_code, msg = process_unhealthy_ports(content)
        if truncate and content.strip():
            obj.truncate_unhealthy_ports(rt.logger)
        rt.finish(exit_code, msg)
