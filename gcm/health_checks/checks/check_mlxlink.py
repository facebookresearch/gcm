# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check IB module/cable health via mlxlink per-lane fault flags and DDM ranges."""

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

# Glob pciconf devices (HCAs), not cable_* devices.
# mlxlink reads module info via the HCA, no `mst cable add` needed.
MST_PCICONF_GLOB = "/dev/mst/mt*pciconf[0-9]*"

# Per-lane fault flags that indicate a hard module/cable failure.
DEFAULT_CRITICAL_FLAGS: tuple[str, ...] = (
    "Module FW Fault",
    "DataPath FW Fault",
    "Tx Fault",
    "Rx LOS",
    "Tx LOS",
)

# Per-lane fault flags that indicate degradation but not yet broken.
DEFAULT_WARN_FLAGS: tuple[str, ...] = (
    "Rx CDR LOL",
    "Tx CDR LOL",
    "Tx Adaptive EQ Fault",
)

HEALTHY_MODULE_STATE = "Ready state"
HEALTHY_DATAPATH_STATE = "DPActivated"

# DDM metrics whose values must fall within the bracketed [min..max] range.
DDM_RANGE_METRICS: tuple[str, ...] = (
    "Temperature",
    "Voltage",
    "Bias Current",
    "Rx Power Current",
    "Tx Power Current",
)


class MlxlinkCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def list_pciconf_devices(self, logger: logging.Logger) -> List[str]:
        """Enumerate MST pciconf device paths (one per HCA)."""
        ...

    def get_module_info(
        self,
        device: str,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Run mlxlink -d <device> -m to fetch module info."""
        ...


@dataclass(frozen=True)
class MlxlinkCheckImpl:
    """Production implementation -- enumerates HCAs and runs mlxlink."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def list_pciconf_devices(self, logger: logging.Logger) -> List[str]:
        """Enumerate MST pciconf device paths."""
        # Filter out cable_* devices that may also match the glob suffix.
        devices = sorted(d for d in glob.glob(MST_PCICONF_GLOB) if "_cable_" not in d)
        logger.info("Found %d pciconf device(s)", len(devices))
        return devices

    def get_module_info(
        self,
        device: str,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Run mlxlink -d <device> -m to fetch module info."""
        cmd = f"mlxlink -d {device} -m"
        logger.info("Running command '%s'", cmd)
        return shell_command(cmd, timeout_secs)


def _parse_flag_lanes(value: str) -> List[int]:
    """Parse a per-lane comma-separated flag value into a list of ints."""
    parts = [p.strip() for p in value.split(",")]
    out: List[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            # Non-numeric (e.g. "N/A") -- treat as 0/healthy.
            out.append(0)
    return out


def _check_flag(
    output: str,
    flag_name: str,
) -> List[int]:
    """Find a flag line in mlxlink output and return its per-lane values.

    Looks for lines like:
        Tx Fault [per lane]                : 0,0,0,0
        Module FW Fault                    : 0
    """
    pattern = rf"^{re.escape(flag_name)}(?: \[per lane\])?\s*:\s*(.+)$"
    match = re.search(pattern, output, re.MULTILINE)
    if not match:
        return []
    return _parse_flag_lanes(match.group(1))


def _parse_ddm_metric(
    output: str,
    metric_name: str,
) -> Optional[Tuple[List[float], float, float]]:
    """Parse a DDM metric line returning (values, min, max).

    Looks for lines like:
        Temperature [C]                    : 49 [-10..80]
        Bias Current [mA]                  : 9.210,9.264 [7..11]

    Returns None if the metric isn't found or has no range.
    """
    pattern = (
        rf"^{re.escape(metric_name)}(?: \[[^\]]+\])?\s*:\s*"
        r"([0-9.,\-]+)\s*\[([\-0-9.]+)\.\.([\-0-9.]+)\]"
    )
    match = re.search(pattern, output, re.MULTILINE)
    if not match:
        return None
    raw_values, raw_min, raw_max = match.groups()
    try:
        values = [float(v) for v in raw_values.split(",") if v.strip()]
        return values, float(raw_min), float(raw_max)
    except ValueError:
        return None


def process_module_info(
    device: str,
    output: str,
    returncode: int,
    critical_flags: Collection[str],
    warn_flags: Collection[str],
    check_ddm_ranges: bool,
) -> Tuple[ExitCode, List[str]]:
    """Evaluate mlxlink output for one HCA. Returns (status, issue_lines)."""
    if returncode:
        return ExitCode.WARN, [f"{device}: mlxlink failed (rc={returncode})"]

    issues: List[str] = []
    status = ExitCode.OK

    # Module / DataPath state
    state_match = re.search(r"^Module State\s*:\s*(.+)$", output, re.MULTILINE)
    if state_match and state_match.group(1).strip() != HEALTHY_MODULE_STATE:
        issues.append(f"{device}: Module State={state_match.group(1).strip()}")
        status = ExitCode.CRITICAL

    dp_match = re.search(
        r"^DataPath state(?: \[per lane\])?\s*:\s*(.+)$", output, re.MULTILINE
    )
    if dp_match:
        dp_states = [s.strip() for s in dp_match.group(1).split(",")]
        bad_dp = [s for s in dp_states if s != HEALTHY_DATAPATH_STATE]
        if bad_dp:
            issues.append(f"{device}: DataPath state={dp_match.group(1).strip()}")
            status = ExitCode.CRITICAL

    # Critical per-lane flags
    for flag in critical_flags:
        lanes = _check_flag(output, flag)
        if any(v != 0 for v in lanes):
            issues.append(f"{device}: {flag}={lanes}")
            status = ExitCode.CRITICAL

    # Warning per-lane flags
    for flag in warn_flags:
        lanes = _check_flag(output, flag)
        if any(v != 0 for v in lanes):
            issues.append(f"{device}: {flag}={lanes}")
            if status < ExitCode.WARN:
                status = ExitCode.WARN

    # DDM range checks
    if check_ddm_ranges:
        for metric in DDM_RANGE_METRICS:
            parsed = _parse_ddm_metric(output, metric)
            if parsed is None:
                continue
            values, lo, hi = parsed
            out_of_range = [v for v in values if v < lo or v > hi]
            if out_of_range:
                issues.append(f"{device}: {metric}={values} outside [{lo}..{hi}]")
                if status < ExitCode.WARN:
                    status = ExitCode.WARN

    return status, issues


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--critical-flags",
    type=click.STRING,
    multiple=True,
    default=DEFAULT_CRITICAL_FLAGS,
    show_default=True,
    help="mlxlink fault flags that escalate to CRITICAL when nonzero.",
)
@click.option(
    "--warn-flags",
    type=click.STRING,
    multiple=True,
    default=DEFAULT_WARN_FLAGS,
    show_default=True,
    help="mlxlink fault flags that escalate to WARN when nonzero.",
)
@click.option(
    "--check-ddm-ranges/--no-check-ddm-ranges",
    default=True,
    show_default=True,
    help="Verify Temperature/Voltage/Bias/Power values fall within reported ranges.",
)
@click.pass_obj
@typechecked
def check_mlxlink(
    obj: Optional[MlxlinkCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    critical_flags: tuple[str, ...],
    warn_flags: tuple[str, ...],
    check_ddm_ranges: bool,
) -> None:
    """Check IB module health via mlxlink per-lane fault flags."""
    if not obj:
        obj = MlxlinkCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_IB_MODULE_HEALTH,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ib_module_health(),
    ) as rt:
        devices = obj.list_pciconf_devices(rt.logger)
        if not devices:
            rt.finish(ExitCode.UNKNOWN, "No IB pciconf devices found")

        overall_exit_code = ExitCode.OK
        all_issues: List[str] = []

        for device in devices:
            try:
                out = obj.get_module_info(device, timeout, rt.logger)
            except Exception as e:
                out = handle_subprocess_exception(e)

            status, issues = process_module_info(
                device,
                out.stdout,
                out.returncode,
                critical_flags,
                warn_flags,
                check_ddm_ranges,
            )
            all_issues.extend(issues)
            if status > overall_exit_code:
                overall_exit_code = status

        if all_issues:
            msg = (
                f"{len(all_issues)} issue(s) across {len(devices)} HCA(s):\n"
                + "\n".join(all_issues)
            )
        else:
            msg = f"All {len(devices)} HCA(s) healthy"
        rt.finish(overall_exit_code, msg)
