# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Group of commands for various process related checks."""

from typing import List

import click
from gcm.health_checks.checks.check_dstate import check_dstate
from gcm.health_checks.checks.check_running_process import check_running_process
from gcm.health_checks.checks.check_zombie import check_zombie


@click.group()
def check_process() -> None:
    """A collection of process related checks."""


list_of_checks: List[click.core.Command] = [
    check_dstate,
    check_running_process,
    check_zombie,
]

for check in list_of_checks:
    check_process.add_command(check)

if __name__ == "__main__":
    check_process()
