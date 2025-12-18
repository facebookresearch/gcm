# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for the check_pci healthcheck."""

import json
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Optional

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_pci import check_pci, PciLink
from gcm.health_checks.types import ExitCode
from gcm.tests.data import health_checks


@dataclass
class FakePciCheckImpl:
    """Fake check-pci health_check implementation for testing."""

    manifest_path: str

    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def read_pci_link(self, pci_slot: str) -> PciLink:
        """Read sysfs device info from a test data file."""
        pci_slot_data = pci_slot.split(":")
        pci_slot_key = ":".join(pci_slot_data[0:2])

        sysfs_device = f"/sys/class/pci_bus/{pci_slot_key}/device/{pci_slot}/"
        sysfs_link_speed = fake_read_sysfs_val(
            sysfs_device + "current_link_speed", self.manifest_path
        )
        sysfs_link_width = fake_read_sysfs_val(
            sysfs_device + "current_link_width", self.manifest_path
        )

        if sysfs_link_speed is not None:
            sysfs_link_speed = sysfs_link_speed.strip()
        if sysfs_link_width is not None:
            sysfs_link_width_int = int(sysfs_link_width.strip())
        else:
            sysfs_link_width_int = None

        return PciLink(pci_slot, sysfs_link_speed, sysfs_link_width_int)

    def read_manifest(self, manifest_file: str) -> dict[str, Any]:
        """Parse the manifest file as JSON and return a dict."""
        with resources.open_text(health_checks, manifest_file) as manifest:
            return json.loads(manifest.read())


def fake_read_sysfs_val(path: str, manifest_path: str) -> Optional[str]:
    """Get a sysfs value from a test datafile instead of from the `/sys` filesystem."""
    pci_data = {}

    with resources.open_text(health_checks, manifest_path) as contents:
        pci_data = json.loads(contents.read())

    def read_value(path: str) -> Optional[str]:
        if path in pci_data:
            return pci_data[path].strip()
        return None

    return read_value(path)


@pytest.fixture
def pci_tester(request: pytest.FixtureRequest) -> FakePciCheckImpl:
    """Create FakePciCheckImpl object."""
    return FakePciCheckImpl(request.param)


@pytest.mark.parametrize(
    "pci_tester, manifest_file, expected",
    [
        (
            "cache_milan_good.json",
            "cache_milan.json",
            (
                ExitCode.OK,
                "PCIe Devices Good",
            ),
        ),
        (
            "empty.json",
            "cache_milan.json",
            (
                ExitCode.CRITICAL,
                "PCIe Issues Detected",
            ),
        ),
        (
            "empty.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "PCIe Issues Detected",
            ),
        ),
        (
            "cache_rome_good.json",
            "cache_rome.json",
            (
                ExitCode.OK,
                "PCIe Devices Good",
            ),
        ),
        (
            "learn_good.json",
            "DGX_A100.json",
            (
                ExitCode.OK,
                "PCIe Devices Good",
            ),
        ),
        (
            "cache_downlink.json",
            "cache_milan.json",
            (
                ExitCode.CRITICAL,
                "has degraded PCIe link",
            ),
        ),
        (
            "compute_samsung980pro-downgraded.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "has degraded PCIe link",
            ),
        ),
        (
            "compute_samsung980pro.json",
            "DGX_A100.json",
            (
                ExitCode.OK,
                "PCIe Devices Good",
            ),
        ),
    ],
    indirect=["pci_tester"],
)
def test_check_pci(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    pci_tester: FakePciCheckImpl,
    manifest_file: str,
    expected: tuple[ExitCode, str],
) -> None:
    """Compare check_pci health-check results with expectations."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_pci,
        f"fair_cluster prolog --log-folder={tmp_path} "
        f"--manifest_file={manifest_file} --sink=do_nothing",
        obj=pci_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
