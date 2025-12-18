# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check IPA registered certs against ones received directly from the server."""

import logging
import re
import subprocess
import sys
from collections.abc import Collection
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from socket import gethostname
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
from gcm.health_checks.subprocess import shell_command, ShellCommandOut
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

##########################
# Module-level constants #
##########################

CMD_IPA = "ipa host-show --raw"
CMD_KEY = "ssh-keyscan -4"
CMD_GEN = "ssh-keygen -lf -"

####################
# Class definition #
####################


class SshCertsCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def get_ipa_certs(self, host: str, timeout_secs: int) -> ShellCommandOut:
        """Get host certificate fingerprints from IPA."""
        ...

    def get_ssh_certs(self, host: str, timeout_secs: int) -> ShellCommandOut:
        """Get host certificate fingerprints via ssh-keyscan and ssh-keygen."""
        ...


########################
# Class implementation #
########################


@dataclass(frozen=True)
class SshCertsCheckImpl:
    """Implement the check-ssh-certs check."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    @staticmethod
    def get_ipa_certs(host: str, timeout_secs: int) -> ShellCommandOut:
        """Get registered host key fingerprints from IPA."""
        return shell_command(f"{CMD_IPA} {host}", timeout_secs)

    @staticmethod
    def get_ssh_certs(host: str, timeout_secs: int) -> ShellCommandOut:
        """Get host certificate fingerprints via ssh-keyscan and ssh-keygen."""
        return shell_command(
            CMD_GEN,
            timeout_secs,
            input=shell_command(
                f"{CMD_KEY} {host}",
                timeout_secs,
            ).stdout,
        )


##########################
# Health check functions #
##########################


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--host",
    type=click.STRING,
    help="Hostname to check ssh certs against IPA",
    required=True,
    multiple=False,
)
@click.pass_obj
@typechecked
def check_ssh_certs(
    obj: Optional[SshCertsCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    host: str,
) -> None:
    """Check hostkeys against ipa certs."""
    node: str = gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=str(Path(log_folder) / f"{type}_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-ssh-certs: cluster: {cluster}, node: {node}, type: {type}, host: {host}"
    )
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")
    if not obj:
        obj = SshCertsCheckImpl(cluster, type, log_level, log_folder)
    check_status = ExitCode.OK
    short_out = ""
    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.CHECK_SSH_CERTS.value,
                node=node,
                get_exit_code_msg=lambda: (check_status, short_out),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_SSH_CERTS,
                lambda: (check_status, short_out),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_ssh_certs():
            check_status = ExitCode.OK
            short_out = "disabled by killswitch"
            log_exit(logger, check_status, short_out)
        try:
            ipa_out = obj.get_ipa_certs(host, timeout)
            if ipa_out.returncode:
                if "host not found" in ipa_out.stdout:
                    check_status = ExitCode.CRITICAL
                    short_out = msg_error(ipa_out, f": Is {host} registered in IPA?")
                else:
                    check_status = ExitCode.UNKNOWN
                    short_out = msg_error(ipa_out, ": Is IPA down?")
                log_exit(logger, check_status, short_out)
        except subprocess.TimeoutExpired as e:
            check_status = ExitCode.UNKNOWN
            short_out = msg_timeout(e, ": Is IPA down?")
            log_exit(logger, check_status, short_out)
        ipa_certs = set(
            re.findall(
                r"(?:\bsshpubkeyfp: )(\S+)(?: [(])",
                ipa_out.stdout,
                re.MULTILINE,
            )
        )
        if not ipa_certs:
            check_status = ExitCode.CRITICAL
            short_out = f"No certs for {host} found in IPA. Is {host} in production?"
            log_exit(logger, check_status, short_out)
        try:
            ssh_out = obj.get_ssh_certs(host, timeout)
            if ssh_out.returncode:
                check_status = ExitCode.CRITICAL
                short_out = msg_error(ssh_out, f"Is {host} down?")
                log_exit(logger, check_status, short_out)
        except subprocess.TimeoutExpired as e:
            check_status = ExitCode.CRITICAL
            short_out = msg_timeout(e)
            log_exit(logger, check_status, short_out)
        ssh_certs = set(
            re.findall(
                r"(?:\b[0-9]+ )(\S+)" f"(?: {host} [(])",
                ssh_out.stdout,
                re.MULTILINE,
            )
        )
        missing_certs = ipa_certs - ssh_certs
        if missing_certs:
            check_status = ExitCode.CRITICAL
            short_out = (
                f"{len(missing_certs)}/{len(ipa_certs)} certs registered in IPA but not "
                f"found in {host} ssh. Was {host} reprovisioned but not re-registered?"
            )
            log_exit(logger, check_status, short_out)
        short_out = f"{len(ipa_certs)} certs registered in IPA and found in {host} ssh."
        log_exit(logger, check_status, short_out)


def log_exit(logger: logging.Logger, check_status: ExitCode, short_out: str) -> None:
    """Log output and exit."""
    check = CheckOutput(
        HealthCheckName.CHECK_SSH_CERTS.value,
        check_status=check_status,
        short_out=short_out,
    )
    logger.info(f"exit code {check_status.value}: {check}")
    sys.exit(check_status.value)


def msg_error(p: ShellCommandOut, extra: Optional[str] = None) -> str:
    """Format an error message for a failed subprocess."""
    cmd = p.args if isinstance(p.args, str) else " ".join(p.args)
    msg = f"Error {p.returncode} running `{cmd}`: {p.stdout}"
    if extra:
        return f"{msg}: {extra}"
    return msg


def msg_timeout(e: subprocess.TimeoutExpired, extra: Optional[str] = None) -> str:
    """Format an error message for a failed subprocess."""
    cmd = e.cmd if isinstance(e.cmd, str) else " ".join(e.cmd)
    msg = f"Timeout in {e.timeout} secs running `{cmd}`: {e.output}"
    if extra:
        return f"{msg}: {extra}"
    return msg
