# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_ib_port_errors health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ib_port_errors import (
    build_hexid_to_hostname,
    check_ib_port_errors,
    process_port_errors,
)
from gcm.health_checks.types import ExitCode

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "health_checks"

SAMPLE_DISCOVER = (DATA_DIR / "ib_discover_sample.txt").read_text()
SAMPLE_PM_CLEAN = (DATA_DIR / "ib_pm_clean.txt").read_text()
SAMPLE_PM_ERRORS = (DATA_DIR / "ib_pm_errors.txt").read_text()
SAMPLE_PM_MULTI_BLOCK = (DATA_DIR / "ib_pm_multi_block.txt").read_text()


@dataclass
class FakeIbPortErrorsCheckImpl:
    pm_content: str
    discover_content: str
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def read_pm_file(self, logger: logging.Logger) -> str:
        return self.pm_content

    def read_discover_file(self, logger: logging.Logger) -> str:
        return self.discover_content


# --- Unit tests ---


class TestBuildHexidToHostname:
    def test_parses_switches(self) -> None:
        result = build_hexid_to_hostname(SAMPLE_DISCOVER)
        assert "0011223344550001" in result
        assert result["0011223344550001"] == "switch0001"


class TestProcessPortErrors:
    def test_clean(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_CLEAN, SAMPLE_DISCOVER, 0)
        assert exit_code == ExitCode.OK

    def test_errors_detected(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_ERRORS, SAMPLE_DISCOVER, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "symbol_error_counter" in msg
        assert "switch0001" in msg

    def test_threshold_filters(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_ERRORS, SAMPLE_DISCOVER, 1000)
        assert exit_code == ExitCode.OK

    def test_empty_pm(self) -> None:
        exit_code, msg = process_port_errors("", SAMPLE_DISCOVER, 0)
        assert exit_code == ExitCode.WARN

    def test_no_discover(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_ERRORS, "", 0)
        assert exit_code == ExitCode.CRITICAL
        assert "Unknown" in msg

    def test_multi_block_finds_all_errors(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_MULTI_BLOCK, SAMPLE_DISCOVER, 0)
        assert exit_code == ExitCode.CRITICAL
        # Should find errors in block 2 (port_rcv_errors=5) and block 3 (symbol_error=26)
        assert "port_rcv_errors" in msg
        assert "symbol_error_counter" in msg
        assert "2 port error" in msg

    def test_multi_block_clean_port_skipped(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_MULTI_BLOCK, SAMPLE_DISCOVER, 0)
        # Block 1 (node001 HCA port) has all zeros — should not appear in errors
        assert "node001" not in msg

    def test_multi_block_switch_name_resolved(self) -> None:
        exit_code, msg = process_port_errors(SAMPLE_PM_MULTI_BLOCK, SAMPLE_DISCOVER, 0)
        # Block 2 switch GUID should resolve to switch0001
        assert "switch0001" in msg
        # Block 3 switch GUID should resolve to switch0002
        assert "switch0002" in msg


# --- Integration tests via CliRunner ---


@pytest.fixture
def port_errors_tester(request: pytest.FixtureRequest) -> FakeIbPortErrorsCheckImpl:
    return FakeIbPortErrorsCheckImpl(**request.param)


@pytest.mark.parametrize(
    "port_errors_tester, expected",
    [
        (
            {"pm_content": SAMPLE_PM_CLEAN, "discover_content": SAMPLE_DISCOVER},
            (ExitCode.OK, "No port errors"),
        ),
        (
            {"pm_content": SAMPLE_PM_ERRORS, "discover_content": SAMPLE_DISCOVER},
            (ExitCode.CRITICAL, "port error"),
        ),
        (
            {"pm_content": "", "discover_content": ""},
            (ExitCode.WARN, "empty"),
        ),
    ],
    indirect=["port_errors_tester"],
)
def test_check_ib_port_errors(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    port_errors_tester: FakeIbPortErrorsCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.set_level(logging.INFO)

    result = runner.invoke(
        check_ib_port_errors,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=port_errors_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
