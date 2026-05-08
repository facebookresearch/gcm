# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Parse ibdiagnet port counter data for IB fabric errors.

This is a cluster-wide check designed to run from a management node
that has recently executed ``ibdiagnet --pc``.  It reads the
performance-monitor file and the topology discovery file produced
by ibdiagnet, cross-references switch hex GUIDs to hostnames, and
reports any non-zero error counters.
"""

import logging
import re
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

DEFAULT_PM_FILE = "/var/tmp/ibdiagnet2/ibdiagnet2.pm"
DEFAULT_DISCOVER_FILE = "/var/tmp/ibdiagnet2/ibdiagnet2.ibnetdiscover"

ERROR_KEYS = (
    "excessive_buffer_overrun_errors_extended",
    "link_error_recovery_counter_extended",
    "local_link_integrity_errors_extended",
    "port_buffer_overrun_errors",
    "port_dlid_mapping_errors",
    "port_local_physical_errors",
    "port_looping_errors",
    "port_malformed_packet_errors",
    "port_rcv_constraint_errors_extended",
    "port_rcv_errors_extended",
    "port_rcv_remote_physical_errors_extended",
    "port_rcv_switch_relay_errors_extended",
    "port_vl_mapping_errors",
    "port_xmit_constraint_errors_extended",
    "symbol_error_counter_extended",
)


class IbPortErrorsCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def read_pm_file(self, logger: logging.Logger) -> str:
        """Read the ibdiagnet performance-monitor file."""
        ...

    def read_discover_file(self, logger: logging.Logger) -> str:
        """Read the ibdiagnet ibnetdiscover file."""
        ...


@dataclass(frozen=True)
class IbPortErrorsCheckImpl:
    """Read ibdiagnet output files for port counter analysis."""

    cluster: str
    type: str
    log_level: str
    log_folder: str
    pm_file: str = DEFAULT_PM_FILE
    discover_file: str = DEFAULT_DISCOVER_FILE

    def read_pm_file(self, logger: logging.Logger) -> str:
        """Read the ibdiagnet performance-monitor file."""
        logger.info("Reading PM file: %s", self.pm_file)
        with open(self.pm_file) as f:
            return f.read()

    def read_discover_file(self, logger: logging.Logger) -> str:
        """Read the ibdiagnet ibnetdiscover file."""
        logger.info("Reading discover file: %s", self.discover_file)
        with open(self.discover_file) as f:
            return f.read()


def build_hexid_to_hostname(discover_content: str) -> Dict[str, str]:
    """Map switch hex GUIDs to hostnames from ibnetdiscover output."""
    hexid_to_hostname: Dict[str, str] = {}
    pattern = re.compile(
        r'Switch\s+\d+\s+"S-(?P<hexid>[^"]+)"\s+#\s+"(?P<name>[^"\s]+)'
    )
    for line in discover_content.split("\n"):
        match = pattern.match(line)
        if match:
            hexid_to_hostname[match.group("hexid")] = match.group("name")
    return hexid_to_hostname


def parse_switch_name(
    port_header: str,
    hexid_to_hostname: Dict[str, str],
) -> str:
    """Extract a human-readable switch name from a Port= header line."""
    # Find the Port Name= or Name= field
    # Real ibdiagnet format: "Port=1 Lid=0x4c14 ... Port Name=Sb8ce.../P2"
    name_match = re.search(r"(?:Port )?Name=(\S+)", port_header)
    name_part = name_match.group(1) if name_match else None

    if name_part is None:
        return port_header.strip()

    segments = name_part.split("/")

    if (
        len(segments) >= 3
        and segments[0].startswith("S")
        and segments[1].startswith("N")
    ):
        hexid = segments[0][1:]
        hostname = hexid_to_hostname.get(hexid, f"Unknown[{hexid}]")
        return f"{hostname}/{segments[2]}"

    return name_part


def process_port_errors(
    pm_content: str,
    discover_content: str,
    error_threshold: int,
) -> Tuple[ExitCode, str]:
    """Parse ibdiagnet PM output and return exit code + message."""
    if not pm_content.strip():
        return ExitCode.WARN, "PM file is empty"

    hexid_to_hostname = build_hexid_to_hostname(discover_content)

    # PM file format: dashed-line, Port= header, dashed-line, counters, ...
    # Capture from Port= line through all counters until the next Port= or EOF
    port_blocks = re.findall(
        r"^Port=.+?(?=^Port=|\Z)", pm_content, re.DOTALL | re.MULTILINE
    )
    if not port_blocks:
        return ExitCode.WARN, "No port data found in PM file"

    errors: List[Tuple[str, str, int]] = []

    for block in port_blocks:
        lines = [line.strip() for line in block.split("\n")]
        if not lines:
            continue

        switch_name = parse_switch_name(lines[0], hexid_to_hostname)

        for line in lines[1:]:
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key not in ERROR_KEYS:
                continue
            if "NA" in value:
                continue

            try:
                count = int(value, 16)
            except ValueError:
                continue

            if count > error_threshold:
                clean_key = key.replace("_extended", "")
                errors.append((switch_name, clean_key, count))

    if not errors:
        return ExitCode.OK, f"No port errors above threshold ({error_threshold})."

    errors.sort(key=lambda t: (-t[2], t[0], t[1]))
    error_lines = [f"{sw}: {err}={cnt}" for sw, err, cnt in errors]
    msg = f"{len(errors)} port error(s) detected:\n" + "\n".join(error_lines)
    return ExitCode.CRITICAL, msg


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--pm-file",
    type=click.Path(),
    default=DEFAULT_PM_FILE,
    help="Path to ibdiagnet2.pm file.",
)
@click.option(
    "--discover-file",
    type=click.Path(),
    default=DEFAULT_DISCOVER_FILE,
    help="Path to ibdiagnet2.ibnetdiscover file.",
)
@click.option(
    "--error-threshold",
    type=click.INT,
    default=0,
    help="Only report errors exceeding this count.",
)
@click.pass_obj
@typechecked
def check_ib_port_errors(
    obj: Optional[IbPortErrorsCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    pm_file: str,
    discover_file: str,
    error_threshold: int,
) -> None:
    """Parse ibdiagnet port counters for fabric errors.

    Run from a management node after ``ibdiagnet --pc``.
    """
    if not obj:
        obj = IbPortErrorsCheckImpl(
            cluster, type, log_level, log_folder, pm_file, discover_file
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
        health_check_name=HealthCheckName.CHECK_IB_PORT_ERRORS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ib_port_errors(),
    ) as rt:
        try:
            pm_content = obj.read_pm_file(rt.logger)
        except FileNotFoundError:
            rt.finish(ExitCode.WARN, f"PM file not found: {pm_file}")
        except Exception as e:
            rt.finish(ExitCode.WARN, f"Error reading PM file: {e}")

        try:
            discover_content = obj.read_discover_file(rt.logger)
        except FileNotFoundError:
            discover_content = ""
            rt.logger.warning("Discover file not found, switch names will be hex IDs")
        except Exception:
            discover_content = ""

        exit_code, msg = process_port_errors(
            pm_content, discover_content, error_threshold
        )
        rt.finish(exit_code, msg)
