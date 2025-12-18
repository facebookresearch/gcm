# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
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
from gcm.health_checks.checks.check_iblink import check_iblink
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    piped_shell_command,
    PipedShellCommandOut,
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
from pydantic import BaseModel
from typeguard import typechecked


@click.group()
def check_ib() -> None:
    """ib status checks. i.e. ib_stat"""


check_ib.add_command(check_iblink)


class IBStat(CheckEnv, Protocol):
    def get_ibstat(
        self,
        use_physical_state: bool,
        iblinks_only: bool,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> PipedShellCommandOut: ...

    def get_ib_interfaces(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut: ...


@dataclass
class IBStatImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_ibstat(
        self,
        use_physical_state: bool,
        iblinks_only: bool,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> PipedShellCommandOut:
        cmd = ["ibstat"]
        if use_physical_state:
            if iblinks_only:
                cmd.append(
                    'awk \'/Physical state:/ { state = $NF } /Link layer:/ { if ($NF == "InfiniBand") print "Physical state:", state; state = "" }\''
                )
            else:
                cmd.append("grep 'Physical state'")
        else:
            if iblinks_only:
                cmd.append(
                    'awk \'/State:/ { state = $NF } /Link layer:/ { if ($NF == "InfiniBand") print "State:", state; state = "" }\''
                )
            else:
                cmd.append("grep 'State'")

        logger.info(f"Running command {' | '.join(cmd)}")
        return piped_shell_command(cmd, timeout_secs)

    def get_ib_interfaces(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        cmd = "ip -json link show"
        logger.info(f"Running command {cmd}")
        return shell_command(
            cmd,
            timeout_secs,
        )


def process_ibstat_output(
    output: str, error_code: int, use_physical_state: bool
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"ibstat command FAILED to execute. error_code: {error_code} output: {output}\n",
        )

    for line in output.splitlines():
        if use_physical_state:
            if "LinkUp" not in line:
                return ExitCode.CRITICAL, "Link status is not LinkUp"
        else:
            if "Active" not in line:
                return ExitCode.CRITICAL, "Link state is not Active"

    return ExitCode.OK, "ib stat reported ok status"


@check_ib.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--physical-state/--state",
    default=True,
    help="Check ibstat for 'Physical state' of the adapter port, or 'State' for the operational state of the adapter",
    show_default=True,
)
@click.option(
    "--iblinks-only/--all-links",
    default=True,
    help="Check ibstat for the ib links or for all the links of the adapter",
    show_default=True,
)
@click.pass_obj
@typechecked
def check_ibstat(
    obj: Optional[IBStat],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    physical_state: bool,
    iblinks_only: bool,
) -> None:
    """Check ibstat for the link status"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(f"check_ibstat:, cluster: {cluster}, node: {node}, type: {type}")
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

    if obj is None:
        obj = IBStatImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_IBSTAT.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_IBSTAT,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_ibstat():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_IBSTAT.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            ibstat_output: PipedShellCommandOut = obj.get_ibstat(
                physical_state, iblinks_only, timeout, logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            ibstat_output = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_ibstat_output(
            ibstat_output.stdout, ibstat_output.returncode[0], physical_state
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


class NetworkInterface(BaseModel):
    ifindex: int
    ifname: str
    flags: List[str]
    mtu: int
    qdisc: str
    operstate: str
    linkmode: str
    group: str
    txqlen: Optional[int]
    link_type: str
    address: str
    broadcast: str
    vfinfo_list: Optional[List[str]]


def process_ib_interfaces_output(
    output: str, error_code: int, expected_interfaces: int
) -> Tuple[ExitCode, str]:
    """Check if the ib interfaces returned equals the expected number"""

    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"ib interfaces command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    try:
        present_interfaces = json.loads(output)
    except ValueError:
        return ExitCode.CRITICAL, f"Invalid output returned: {output}"

    network_interfaces = [NetworkInterface(**item) for item in present_interfaces]
    ib_interfaces = 0
    for interface in network_interfaces:
        if interface.link_type == "infiniband" and interface.operstate == "UP":
            ib_interfaces += 1

    if ib_interfaces != expected_interfaces:
        msg = f"Number of interfaces present, {ib_interfaces}, is different than expected, {expected_interfaces}\n"
        return ExitCode.CRITICAL, msg

    msg = f"Number of ib interfaces present is the same as expected, {expected_interfaces}\n"
    return ExitCode.OK, msg


@check_ib.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option("--interface-num", type=click.INT, default=8)
@click.pass_obj
@typechecked
def check_ib_interfaces(
    obj: Optional[IBStat],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    interface_num: int,
) -> None:
    """Check ib-interfaces for the link status"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check_ib_interfaces:, cluster: {cluster}, node: {node}, type: {type} interface_num: {interface_num}"
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

    if obj is None:
        obj = IBStatImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_IB_INTERFACES.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_IB_INTERFACES,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_ib_interfaces():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_IB_INTERFACES.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            ib_interfaces_output: ShellCommandOut = obj.get_ib_interfaces(
                timeout, logger
            )
        except Exception as e:
            ib_interfaces_output = handle_subprocess_exception(e)

        exit_code, msg = process_ib_interfaces_output(
            ib_interfaces_output.stdout,
            ib_interfaces_output.returncode,
            interface_num,
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)
