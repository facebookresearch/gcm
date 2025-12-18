# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Group of commands for various cuda related checks."""

from typing import List

import click

from gcm.health_checks.checks.check_memtest import memtest


@click.group()
def cuda() -> None:
    """A collection of CUDA related checks."""


list_of_checks: List[click.core.Command] = [
    memtest,
]

for check in list_of_checks:
    cuda.add_command(check)

if __name__ == "__main__":
    cuda()
