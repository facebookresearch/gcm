# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_ufm_health health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ufm_health import (
    check_ufm_health,
    process_unhealthy_ports,
)
from gcm.health_checks.types import ExitCode

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "health_checks"

SAMPLE_UNHEALTHY_PORTS = (DATA_DIR / "ib_unhealthy_ports.txt").read_text()


@dataclass
class FakeUfmHealthCheckImpl:
    content: str
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def read_unhealthy_ports(self, logger: logging.Logger) -> str:
        return self.content

    def truncate_unhealthy_ports(self, logger: logging.Logger) -> None:
        pass


# --- Unit tests ---


class TestProcessUnhealthyPorts:
    def test_empty(self) -> None:
        exit_code, msg = process_unhealthy_ports("")
        assert exit_code == ExitCode.OK
        assert "No unhealthy" in msg

    def test_whitespace_only(self) -> None:
        exit_code, msg = process_unhealthy_ports("   \n  \n  ")
        assert exit_code == ExitCode.OK

    def test_header_only(self) -> None:
        content = "# NodeGUID, PortNum, NodeDesc, PeerNodeGUID, PeerPortNum, PeerNodeDesc, {Conditions}, TimeStamp\n"
        exit_code, msg = process_unhealthy_ports(content)
        assert exit_code == ExitCode.OK
        assert "No unhealthy" in msg

    def test_real_format_single_port(self) -> None:
        content = (
            "# NodeGUID, PortNum, NodeDesc, PeerNodeGUID, PeerPortNum, PeerNodeDesc, {Conditions}, TimeStamp\n"
            '0x0011223344550001, 25, "spine-sw-03", 0x0055667788990001, 25, "leaf-sw-38", {FLAPPING}, Fri Mar 20 01:13:40 2026\n'
        )
        exit_code, msg = process_unhealthy_ports(content)
        assert exit_code == ExitCode.CRITICAL
        assert "1 unhealthy" in msg
        assert "FLAPPING" in msg
        assert "spine-sw-03" in msg

    def test_real_format_from_fixture(self) -> None:
        exit_code, msg = process_unhealthy_ports(SAMPLE_UNHEALTHY_PORTS)
        assert exit_code == ExitCode.CRITICAL
        assert "4 unhealthy" in msg
        assert "FLAPPING" in msg

    def test_multiple_conditions(self) -> None:
        content = (
            "# header\n"
            '0x001122, 1, "sw1", 0x334455, 2, "sw2", {FLAPPING, NOISY}, Fri Mar 20 01:00:00 2026\n'
        )
        exit_code, msg = process_unhealthy_ports(content)
        assert exit_code == ExitCode.CRITICAL
        assert "1 unhealthy" in msg

    def test_truncation(self) -> None:
        header = "# header\n"
        lines = "".join(
            f'0x{i:012x}, {i}, "sw{i}", 0x{i+100:012x}, {i}, "sw{i+100}", {{FLAPPING}}, Fri Mar 20 01:00:00 2026\n'
            for i in range(30)
        )
        exit_code, msg = process_unhealthy_ports(header + lines)
        assert exit_code == ExitCode.CRITICAL
        assert "30 unhealthy" in msg
        assert "10 more" in msg


# --- Integration tests via CliRunner ---


@pytest.fixture
def ufm_health_tester(request: pytest.FixtureRequest) -> FakeUfmHealthCheckImpl:
    return FakeUfmHealthCheckImpl(request.param)


@pytest.mark.parametrize(
    "ufm_health_tester, expected",
    [
        (
            "",
            (ExitCode.OK, "No unhealthy"),
        ),
        (
            SAMPLE_UNHEALTHY_PORTS,
            (ExitCode.CRITICAL, "4 unhealthy"),
        ),
        (
            "# header comment only\n",
            (ExitCode.OK, "No unhealthy"),
        ),
    ],
    indirect=["ufm_health_tester"],
)
def test_check_ufm_health(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ufm_health_tester: FakeUfmHealthCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.set_level(logging.INFO)

    result = runner.invoke(
        check_ufm_health,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=ufm_health_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
