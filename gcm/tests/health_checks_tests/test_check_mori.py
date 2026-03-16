# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_mori import (
    check_mori,
    process_mori_output,
)
from gcm.health_checks.cli.health_checks import health_checks as hc_main
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.tests.fakes import FakeShellCommandOut


def test_process_mori_output_success() -> None:
    out = FakeShellCommandOut([], 0, "MORI smoke OK\n")
    result = process_mori_output(out, "smoke")
    assert result.exitcode == ExitCode.OK
    assert "ran successfully" in result.message
    assert "MORI smoke OK" in (result.stdout or "")


def test_process_mori_output_failed_run() -> None:
    out = FakeShellCommandOut([], 1, "ModuleNotFoundError: No module named 'mori'")
    result = process_mori_output(out, "smoke")
    assert result.exitcode == ExitCode.CRITICAL
    assert "FAILED to run" in result.message


def test_check_mori_successful(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_runner(cmd: str, timeout: int) -> ShellCommandOut:
        return FakeShellCommandOut([], 0, "MORI smoke OK\n")

    result = runner.invoke(
        check_mori,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=mock_runner,
    )
    assert result.exit_code == ExitCode.OK.value
    assert "MORI smoke OK" in caplog.text or "MORI Test" in caplog.text


def test_check_mori_failure(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_runner(cmd: str, timeout: int) -> ShellCommandOut:
        return FakeShellCommandOut([], 1, "No module named 'mori'")

    result = runner.invoke(
        check_mori,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=mock_runner,
    )
    assert result.exit_code == ExitCode.CRITICAL.value


def test_check_mori_exception(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    def mock_runner(cmd: str, timeout: int) -> ShellCommandOut:
        raise subprocess.TimeoutExpired(cmd, timeout)

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_mori,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=mock_runner,
    )

    assert result.exit_code == ExitCode.CRITICAL.value
    assert "MORI Test" in caplog.text and "FAILED" in caplog.text


def test_check_mori_disabled_by_killswitch(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Invoke full health_checks group so --features-config is applied (parent sets config_path)."""
    config_path = tmp_path / "features.toml"
    config_path.write_text(
        """
[HealthChecksFeatures]
disable_mori_tests = true
"""
    )
    runner = CliRunner(mix_stderr=False)
    try:
        result = runner.invoke(
            hc_main,
            f"--features-config={config_path} check-mori fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
            catch_exceptions=False,
        )
        assert result.exit_code == ExitCode.OK.value
        assert "disabled by killswitch" in caplog.text
    finally:
        FeatureValueHealthChecksFeatures.config_path = None
