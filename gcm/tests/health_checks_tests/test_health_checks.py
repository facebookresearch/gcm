# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import pytest
from click.testing import CliRunner

from gcm.health_checks.cli.health_checks import health_checks as hc_main


@pytest.mark.parametrize("command", hc_main.commands.keys())
def test_cli(command: str) -> None:
    runner = CliRunner()
    result = runner.invoke(hc_main, [command, "--help"], catch_exceptions=False)

    assert result.stdout.strip() != ""
