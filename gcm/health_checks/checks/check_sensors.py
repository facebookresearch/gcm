# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Invoke ipmi-sensors to detect fan and psu errors."""

import enum
import logging
import re
import socket
import sys
from collections.abc import Collection
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from subprocess import SubprocessError
from typing import Optional, Protocol

import click

import gni_lib

from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.output_utils import CheckOutput
from gcm.health_checks.check_utils.telem import TelemetryContext
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
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

SDR_CACHE = "/var/cache/ipmimonitoringsdrcache/sdr.cache"
SENSOR_TYPES = "Fan,Power_Supply"
MANIFEST = "/etc/manifest.json"


class SensorType(enum.Enum):
    """Provide some constants."""

    FAN = enum.auto()
    PSU = enum.auto()
    PSR = enum.auto()


class SensorsCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def get_sensors(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Invoke ipmi-sensors to read sensor data."""
        ...


def add_error(errors: set[int], sensor_name: str) -> set[int]:
    """Extract digits from the sensor_name and include it in the error set."""
    if matches := re.search(r"[0-9]+", sensor_name):
        errors.add(int(matches.group()))
    else:
        errors.add(-1)
    return errors


def format_expected(msg: str, expected: str) -> str:
    """Format sensor messages."""
    # Strip expected (OK) messages.
    msg = re.sub(f" '{expected}'", "", msg, flags=re.IGNORECASE)
    return f"{msg} (Expected '{expected}')"


def process_sensors_out(output: str, error_code: int) -> CheckOutput:
    """Parse ipmi-sensors output for error conditions."""
    if error_code:
        return CheckOutput(
            "check_sensors",
            check_status=ExitCode.WARN,
            short_out=(
                "ipmi-sensors command FAILED to execute."
                f" error_code: {error_code}"
                f" output: {output}\n"
            ),
        )
    sensors_errors = [
        (
            # Match any fan status that is not EXACTLY "ok"
            re.compile(
                # Capture the sensor name and speed. removed multi-fan checks from the results, they are invalid.
                r"^[^,]+,([^,]+_fan_[^,]+),fan,"
                # Capture the fan speed and unit.
                r"([^,]+),([^,]+),"
                # Skip any leading 'ok' status(es).
                r"(?:'ok' ?)*"
                # Capture the not-ok and subsequent status(es)
                r"('(?!ok)[^']+'(?: '[^']+')*)$",
                re.IGNORECASE | re.MULTILINE,
            ),
            "Error in %s: %s%s %s",
            "OK",
            SensorType.FAN,
        ),
        (
            # Match any power status not EXACTLY 'ok'
            re.compile(
                # Sensor name contains 'pin', 'pout', or 'pwr'
                r"^[^,]+,([^,]*p(?:in|out|wr)[^,]*),power supply,"
                # Capture the power value and unit.
                r"([^,]+),([^,]+),"
                # Skip any leading 'ok' status(es).
                r"(?:'ok' ?)*"
                # Capture the not-ok and subsequent status(es).
                r"('(?!ok)[^']+'(?: '[^']+')*)$",
                re.IGNORECASE | re.MULTILINE,
            ),
            "Error in %s: %s%s %s",
            "OK",
            SensorType.PSU,
        ),
        (
            # Match any PSU status not EXACTLY 'presence detected'
            re.compile(
                # Sensor name contains 'status'
                r"^[^,]+,([^,]*status[^,]*),power supply,"
                # Skip the N/A power output and unit.
                r"[^,]+,[^,]+,"
                # Skip any leading 'presence detected' status(es).
                r"(?:'presence detected' ?)*"
                # Capture the not-presence-detected and subsequent status(es).
                r"('(?!presence detected)[^']+'(?: '[^']+')*)$",
                re.IGNORECASE | re.MULTILINE,
            ),
            "Error in %s: %s",
            "Presence detected",
            SensorType.PSU,
        ),
        (
            # Match any redundancy status not EXACTLY 'fully redundant'
            re.compile(
                # Sensor name contains 'redundancy'
                r"^[^,]+,([^,]*redundancy[^,]*),power supply,"
                # Skip the N/A power output and unit.
                r"[^,]+,[^,]+,"
                # Skip any leading 'fully redundant' status(es).
                r"(?:'fully redundant' ?)*"
                # Capture the not-fully-redundant and subsequent status(es).
                r"('(?!fully redundant)[^']+'(?: '[^']+')*)$",
                re.IGNORECASE | re.MULTILINE,
            ),
            "Error in %s: %s",
            "Fully Redundant",
            SensorType.PSR,
        ),
    ]
    msg: list[str] = []
    status = ExitCode.UNKNOWN
    for error, templ, expected, sensor_type in sensors_errors:
        if matches := re.findall(error, output):
            status = max(
                status,
                ExitCode.WARN if sensor_type == SensorType.PSR else ExitCode.CRITICAL,
            )
            msg.extend(format_expected(templ % groups, expected) for groups in matches)
    if msg:
        return CheckOutput(
            "check_sensors",
            check_status=status,
            long_out=msg,
            short_out=f"{len(msg)} ipmi-sensor error{'s' if len(msg) > 1 else ''}: ",
        )
    return CheckOutput(
        "check_sensors",
        check_status=ExitCode.OK,
        short_out="No ipmi-sensor errors.",
    )


@dataclass
class SensorsCheckImpl:
    """Implement the ipmi-sensors check."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_sensors(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Invoke ipmi-sensors to read sensor data."""
        cmd = (
            "sudo ipmi-sensors"
            " --comma-separated-output"
            " --no-header-output"
            " --quiet-cache"
            " --sdr-cache-recreate"
            f" --sdr-cache-file {SDR_CACHE}"
            f" --sensor-types {SENSOR_TYPES}"
        )
        logger.info("Running command '%s'", cmd)
        return shell_command(cmd, timeout_secs)


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def check_sensors(
    obj: Optional[SensorsCheck],
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
    """Invoke ipmi-sensors and return the output."""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=str(Path(log_folder) / type / "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        "check-sensors: cluster: %s, node: %s, type: %s",
        cluster,
        node,
        type,
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

    if not obj:
        obj = SensorsCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_SENSORS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_SENSORS,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_sensors():
            exit_code = ExitCode.OK
            logger.info(
                "%s is disabled by killswitch",
                HealthCheckName.CHECK_SENSORS.value,
            )
            sys.exit(exit_code.value)
        try:
            sensors_out: ShellCommandOut = obj.get_sensors(timeout, logger)
        except SubprocessError as e:
            sensors_out = handle_subprocess_exception(e)

        check = process_sensors_out(sensors_out.stdout, sensors_out.returncode)
        exit_code = check.check_status
        msg = str(check)

        logger.info("exit code %d: %s", check.check_status.value, check)

        sys.exit(exit_code.value)
