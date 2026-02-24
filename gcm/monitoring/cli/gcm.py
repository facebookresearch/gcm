# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""A single entrypoint into various gcm scripts.

This file is intentionally lightweight and should not include any complex logic.
"""

import click

from gcm._version import __version__
from gcm.monitoring.cli import (
    nvml_monitor,
    sacct_backfill,
    sacct_publish,
    sacct_running,
    sacct_wrapper,
    sacctmgr_qos,
    sacctmgr_user,
    scontrol,
    scontrol_config,
    slurm_job_monitor,
    slurm_monitor,
    sprio,
    sshare,
    storage,
)
from gcm.monitoring.click import DaemonGroup, detach_option, toml_config_option


@click.group(cls=DaemonGroup, epilog=f"GCM Version: {__version__}")
@toml_config_option("gcm")
@detach_option
@click.version_option(__version__)
def main(detach: bool) -> None:
    """GPU cluster monitoring. A toolkit for HPC cluster telemetry and health checks."""


main.add_command(nvml_monitor.main, name="nvml_monitor")
main.add_command(sacct_running.main, name="sacct_running")
main.add_command(sacct_publish.main, name="sacct_publish")
main.add_command(sacct_wrapper.main, name="fsacct")
main.add_command(sacctmgr_qos.main, name="sacctmgr_qos")
main.add_command(sacctmgr_user.main, name="sacctmgr_user")
main.add_command(slurm_job_monitor.main, name="slurm_job_monitor")
main.add_command(slurm_monitor.main, name="slurm_monitor")
main.add_command(sacct_backfill.main, name="sacct_backfill")
main.add_command(scontrol.main, name="scontrol")
main.add_command(scontrol_config.main, name="scontrol_config")
main.add_command(sprio.main, name="sprio")
main.add_command(sshare.main, name="sshare")
main.add_command(storage.main, name="storage")

if __name__ == "__main__":
    main()
