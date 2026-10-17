# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_mlxlink health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_mlxlink import (
    check_mlxlink,
    DEFAULT_CRITICAL_FLAGS,
    DEFAULT_WARN_FLAGS,
    process_module_info,
)
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut

# Realistic mlxlink -m output for a healthy CX-7 OSFP module.
HEALTHY_OUTPUT = """
Operational Info
----------------
State                              : Active
Physical state                     : N/A

Module Info
-----------
Temperature [C]                    : 49 [-10..80]
Voltage [mV]                       : 3189.4 [3100..3500]
Bias Current [mA]                  : 9.210,9.264,9.054,9.142 [7..11]
Rx Power Current [dBm]             : 1.945,1.892,2.167,2.025 [-5.003..3.998]
Tx Power Current [dBm]             : 0.867,1.139,1.011,1.069 [-3.468..3.998]
Module State                       : Ready state
DataPath state [per lane]          : DPActivated,DPActivated,DPActivated,DPActivated
Module FW Fault                    : 0
DataPath FW Fault                  : 0
Tx Fault [per lane]                : 0,0,0,0
Tx LOS [per lane]                  : 0,0,0,0
Tx CDR LOL [per lane]              : 0,0,0,0
Rx LOS [per lane]                  : 0,0,0,0
Rx CDR LOL [per lane]              : 0,0,0,0
Tx Adaptive EQ Fault [per lane]    : 0,0,0,0
"""

# Output with Rx LOS on lane 2 (critical).
RX_LOS_OUTPUT = HEALTHY_OUTPUT.replace(
    "Rx LOS [per lane]                  : 0,0,0,0",
    "Rx LOS [per lane]                  : 0,0,1,0",
)

# Output with Tx CDR LOL on lane 0 (warn).
CDR_LOL_OUTPUT = HEALTHY_OUTPUT.replace(
    "Tx CDR LOL [per lane]              : 0,0,0,0",
    "Tx CDR LOL [per lane]              : 1,0,0,0",
)

# Output with Bias Current above the upper bound (warn).
BIAS_HIGH_OUTPUT = HEALTHY_OUTPUT.replace(
    "Bias Current [mA]                  : 9.210,9.264,9.054,9.142 [7..11]",
    "Bias Current [mA]                  : 9.210,12.5,9.054,9.142 [7..11]",
)

# Output with Module State degraded (critical).
BAD_MODULE_STATE_OUTPUT = HEALTHY_OUTPUT.replace(
    "Module State                       : Ready state",
    "Module State                       : Low Power state",
)


@dataclass
class FakeMlxlinkCheckImpl:
    devices: List[str]
    module_outputs: dict[str, FakeShellCommandOut]
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def list_pciconf_devices(self, logger: logging.Logger) -> List[str]:
        return self.devices

    def get_module_info(
        self, device: str, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.module_outputs[device]


# --- Unit tests for process_module_info ---


class TestProcessModuleInfo:
    def test_healthy(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            HEALTHY_OUTPUT,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.OK
        assert issues == []

    def test_rx_los_critical(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            RX_LOS_OUTPUT,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.CRITICAL
        assert any("Rx LOS" in i for i in issues)

    def test_cdr_lol_warn(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            CDR_LOL_OUTPUT,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.WARN
        assert any("Tx CDR LOL" in i for i in issues)

    def test_bias_out_of_range_warn(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            BIAS_HIGH_OUTPUT,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.WARN
        assert any("Bias Current" in i and "outside" in i for i in issues)

    def test_ddm_range_check_disabled(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            BIAS_HIGH_OUTPUT,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=False,
        )
        assert status == ExitCode.OK

    def test_bad_module_state_critical(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            BAD_MODULE_STATE_OUTPUT,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.CRITICAL
        assert any("Module State" in i for i in issues)

    def test_mlxlink_failure(self) -> None:
        status, issues = process_module_info(
            "mt4129_pciconf0",
            "",
            1,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.WARN
        assert any("mlxlink failed" in i for i in issues)

    def test_critical_outranks_warn(self) -> None:
        # Output has both a critical (Rx LOS) and a warn (CDR LOL) condition.
        combined = RX_LOS_OUTPUT.replace(
            "Tx CDR LOL [per lane]              : 0,0,0,0",
            "Tx CDR LOL [per lane]              : 1,0,0,0",
        )
        status, _ = process_module_info(
            "mt4129_pciconf0",
            combined,
            0,
            DEFAULT_CRITICAL_FLAGS,
            DEFAULT_WARN_FLAGS,
            check_ddm_ranges=True,
        )
        assert status == ExitCode.CRITICAL


# --- Integration tests via CliRunner ---


@pytest.fixture
def mlxlink_tester(request: pytest.FixtureRequest) -> FakeMlxlinkCheckImpl:
    return request.param


@pytest.mark.parametrize(
    "mlxlink_tester, expected_exit",
    [
        (
            FakeMlxlinkCheckImpl(
                devices=["mt4129_pciconf0", "mt4129_pciconf1"],
                module_outputs={
                    "mt4129_pciconf0": FakeShellCommandOut(
                        returncode=0, stdout=HEALTHY_OUTPUT
                    ),
                    "mt4129_pciconf1": FakeShellCommandOut(
                        returncode=0, stdout=HEALTHY_OUTPUT
                    ),
                },
            ),
            ExitCode.OK,
        ),
        (
            FakeMlxlinkCheckImpl(
                devices=["mt4129_pciconf0"],
                module_outputs={
                    "mt4129_pciconf0": FakeShellCommandOut(
                        returncode=0, stdout=RX_LOS_OUTPUT
                    ),
                },
            ),
            ExitCode.CRITICAL,
        ),
        (
            FakeMlxlinkCheckImpl(
                devices=["mt4129_pciconf0"],
                module_outputs={
                    "mt4129_pciconf0": FakeShellCommandOut(
                        returncode=0, stdout=CDR_LOL_OUTPUT
                    ),
                },
            ),
            ExitCode.WARN,
        ),
    ],
    indirect=["mlxlink_tester"],
)
def test_check_mlxlink(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    mlxlink_tester: FakeMlxlinkCheckImpl,
    expected_exit: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.set_level(logging.INFO)

    result = runner.invoke(
        check_mlxlink,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=mlxlink_tester,
    )

    assert result.exit_code == expected_exit.value
