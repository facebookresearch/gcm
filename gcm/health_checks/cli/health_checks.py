# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""A single entrypoint into various health check scripts.

This file is intentionally lightweight and should not include any complex logic.
"""

from typing import List

import click
from gcm._version import __version__
from gcm.health_checks import checks
from gcm.health_checks.click import DEFAULT_CONFIG_PATH

from gcm.monitoring.click import (
    DaemonGroup,
    detach_option,
    feature_flags_config,
    toml_config_option,
)
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)


@click.group(cls=DaemonGroup, epilog=f"health_checks version: {__version__}")
@feature_flags_config(FeatureValueHealthChecksFeatures)
@toml_config_option("health_checks", default_config_path=DEFAULT_CONFIG_PATH)
@detach_option
@click.version_option(__version__)
def health_checks(detach: bool) -> None:
    """GPU Cluster Monitoring: Large-Scale AI Research Cluster Monitoring."""


list_of_checks: List[click.core.Command] = [
    checks.check_ssh_certs,
    checks.check_airstore,
    checks.check_telemetry,
    checks.check_dcgmi,
    checks.check_hca,
    checks.check_nccl,
    checks.check_nvidia_smi,
    checks.check_syslogs,
    checks.check_process,
    checks.cuda,
    checks.check_storage,
    checks.check_processor,
    checks.check_ipmitool,
    checks.check_service,
    checks.check_ib,
    checks.check_authentication,
    checks.check_node,
    checks.check_pci,
    checks.check_blockdev,
    checks.check_ethlink,
    checks.check_sensors,
]

for check in list_of_checks:
    health_checks.add_command(check)

if __name__ == "__main__":
    health_checks()
