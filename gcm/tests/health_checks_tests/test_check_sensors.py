# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_sensors health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_sensors import check_sensors
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode

from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeSensorsCheckImpl:
    """Supply pregenerated output instead of calling ipmi-sensors."""

    sensors_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_sensors(
        self,
        _timeout_secs: int,
        _logger: logging.Logger,
    ) -> ShellCommandOut:
        """Return pregenerated output instead of calling ipmi-sensors."""
        return self.sensors_out


@pytest.fixture
def sensors_tester(
    request: pytest.FixtureRequest,
) -> FakeSensorsCheckImpl:
    """Create FakeSensorsCheckImpl object."""
    return FakeSensorsCheckImpl(request.param)


error_sensors = FakeShellCommandOut(
    [],
    1,
    "Error message",
)
fail_fan_1 = FakeShellCommandOut(
    [],
    0,
    "01,SPD_FAN_SYS1_F,Fan,0.00,RPM,'problem1' 'problem2'",
)
fail_fan_2 = FakeShellCommandOut(
    [],
    0,
    "01,SPD_FAN_SYS2_F,Fan,0.00,RPM,'OK' 'problem1' 'OK' 'problem2'",
)
fail_fan_3 = FakeShellCommandOut(
    [],
    0,
    "01,SPD_FAN_SYS3_F,Fan,0.00,RPM,'problem1' 'OK' 'problem2' 'OK'",
)
fail_psr_1 = FakeShellCommandOut(
    [],
    0,
    "05,REDUNDANCY_PSU,Power Supply,N/A,N/A,'problem1' 'problem2'",
)
fail_psr_2 = FakeShellCommandOut(
    [],
    0,
    "05,PSU_REDUNDANCY,Power Supply,N/A,N/A,'Fully Redundant' 'problem1' 'problem2'",
)
fail_psr_3 = FakeShellCommandOut(
    [],
    0,
    "05,REDUNDANCY,Power Supply,N/A,N/A,'problem1' 'problem2' 'Fully Redundant'",
)
fail_psr_and_psu = FakeShellCommandOut(
    [],
    0,
    "70,PWR_PSU0,Power Supply,0.00,W,'At or Below (<=) Lower Critical Threshold'\n"
    "71,PWR_PSU1,Power Supply,780.00,W,'OK'\n"
    "93,STATUS_PSU0,Power Supply,N/A,N/A,'Presence detected'\n"
    "94,STATUS_PSU1,Power Supply,N/A,N/A,'Presence detected'\n"
    "180,REDUNDANCY_PSU,Power Supply,N/A,N/A,'Redundancy Degraded'\n"
    "99,REDUNDANCY_PSU,Power Supply,N/A,N/A,'Redundancy Lost' 'Non-redundant:Sufficient Resources from Redundant'\n",
)
fail_psu_1 = FakeShellCommandOut(
    [],
    0,
    "03,PSU01_Status,Power Supply,N/A,N/A,'problem1' 'problem2'",
)
fail_psu_2 = FakeShellCommandOut(
    [],
    0,
    "03,PSU02_Status,Power Supply,N/A,N/A,'Presence detected' 'problem1' 'Presence detected' 'problem2'",
)
fail_psu_3 = FakeShellCommandOut(
    [],
    0,
    "03,PSU03_Status,Power Supply,N/A,N/A,'problem1' 'Presence detected' 'problem2' 'Presence detected'",
)
fail_pwr_1 = FakeShellCommandOut(
    [],
    0,
    "01,PSU01_PIN,Power Supply,99.00,W,'problem1' 'problem2'",
)
fail_pwr_2 = FakeShellCommandOut(
    [],
    0,
    "02,PSU02_POUT,Power Supply,99.00,W,'OK' 'problem1' 'OK' 'problem2'",
)
fail_pwr_3 = FakeShellCommandOut(
    [],
    0,
    "02,PSU03_PWR,Power Supply,99.00,W,'problem1' 'OK' 'problem2' 'OK'",
)
pass_all = FakeShellCommandOut(
    [],
    0,
    """00,SPD_FAN_SYS0_R,Fan,9999.00,RPM,'OK'
01,SPD_FAN_SYS0_F,Fan,9999.00,RPM,'OK'
02,SPD_FAN_SYS1_R,Fan,9999.00,RPM,'OK'
03,SPD_FAN_SYS1_F,Fan,9999.00,RPM,'OK'
04,PSU01_PIN,Power Supply,99.00,W,'OK'
05,PSU01_POUT,Power Supply,99.00,W,'OK'
06,PSU01_Status,Power Supply,N/A,N/A,'Presence detected'
07,PWR_PSU02,Power Supply,99.00,W,'OK'
08,REDUNDANCY_PSU,Power Supply,N/A,N/A,'Fully Redundant'
09,STATUS_PSU02,Power Supply,N/A,N/A,'Presence detected'""",
)


@pytest.mark.parametrize(
    ("sensors_tester", "expected"),
    [
        (
            error_sensors,
            (
                ExitCode.WARN,
                "ipmi-sensors command FAILED to execute."
                " error_code: 1"
                " output: Error message",
            ),
        ),
        (
            fail_fan_1,
            (
                ExitCode.CRITICAL,
                "Error in SPD_FAN_SYS1_F:"
                " 0.00RPM 'problem1' 'problem2' (Expected 'OK')",
            ),
        ),
        (
            fail_fan_2,
            (
                ExitCode.CRITICAL,
                "Error in SPD_FAN_SYS2_F:"
                " 0.00RPM 'problem1' 'problem2' (Expected 'OK')",
            ),
        ),
        (
            fail_fan_3,
            (
                ExitCode.CRITICAL,
                "Error in SPD_FAN_SYS3_F:"
                " 0.00RPM 'problem1' 'problem2' (Expected 'OK')",
            ),
        ),
        (
            fail_psr_1,
            (
                ExitCode.WARN,
                "Error in REDUNDANCY_PSU: 'problem1' 'problem2' (Expected 'Fully Redundant')",
            ),
        ),
        (
            fail_psr_2,
            (
                ExitCode.WARN,
                "Error in PSU_REDUNDANCY: 'problem1' 'problem2' (Expected 'Fully Redundant')",
            ),
        ),
        (
            fail_psr_3,
            (
                ExitCode.WARN,
                "Error in REDUNDANCY: 'problem1' 'problem2' (Expected 'Fully Redundant')",
            ),
        ),
        (
            fail_psr_and_psu,
            (
                ExitCode.CRITICAL,
                "Error in PWR_PSU0: 0.00W 'At or Below (<=) Lower Critical Threshold' (Expected 'OK')\n"
                "Error in REDUNDANCY_PSU: 'Redundancy Degraded' (Expected 'Fully Redundant')\n"
                "Error in REDUNDANCY_PSU: 'Redundancy Lost' 'Non-redundant:Sufficient Resources from Redundant' (Expected 'Fully Redundant')",
            ),
        ),
        (
            fail_psu_1,
            (
                ExitCode.CRITICAL,
                "Error in PSU01_Status: 'problem1' 'problem2' (Expected 'Presence detected')",
            ),
        ),
        (
            fail_psu_2,
            (
                ExitCode.CRITICAL,
                "Error in PSU02_Status: 'problem1' 'problem2' (Expected 'Presence detected')",
            ),
        ),
        (
            fail_psu_3,
            (
                ExitCode.CRITICAL,
                "Error in PSU03_Status: 'problem1' 'problem2' (Expected 'Presence detected')",
            ),
        ),
        (
            fail_pwr_1,
            (
                ExitCode.CRITICAL,
                "Error in PSU01_PIN: 99.00W 'problem1' 'problem2' (Expected 'OK')",
            ),
        ),
        (
            fail_pwr_2,
            (
                ExitCode.CRITICAL,
                "Error in PSU02_POUT: 99.00W 'problem1' 'problem2' (Expected 'OK')",
            ),
        ),
        (
            fail_pwr_3,
            (
                ExitCode.CRITICAL,
                "Error in PSU03_PWR: 99.00W 'problem1' 'problem2' (Expected 'OK')",
            ),
        ),
        (pass_all, (ExitCode.OK, "No ipmi-sensor errors.")),
    ],
    indirect=["sensors_tester"],
)
def test_check_sensors(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    sensors_tester: FakeSensorsCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    """Invoke the check_sensors method."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_sensors,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=sensors_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
