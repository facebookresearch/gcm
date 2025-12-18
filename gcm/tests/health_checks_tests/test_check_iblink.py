# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_iblink import check_iblink, IBLinkIssue, IBLinkState
from gcm.health_checks.checks.check_pci import PciDevice
from gcm.health_checks.types import ExitCode
from gcm.tests.data import health_checks


@dataclass
class FakeIBLinkCheckImpl:
    manifest_path: str

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def read_manifest(self, manifest_file: str) -> Dict[str, Any]:
        with resources.open_text(health_checks, manifest_file) as manifest:
            return json.loads(manifest.read())

    def read_cardstate(self, pci_id: str, pci_info: PciDevice) -> IBLinkState:
        sysfs_path = f"/sys/bus/pci/devices/{pci_id}"

        mlx5 = fake_list_sysfs_dir(
            f"{sysfs_path}/infiniband", self.manifest_path, default=["UNKNOWN"]
        )[0]
        ibdev = fake_list_sysfs_dir(
            f"{sysfs_path}/net", self.manifest_path, default=["UNKNOWN"]
        )[0]

        return IBLinkState(
            slot_id=pci_info.slot,
            pci_id=pci_id,
            ib_id=ibdev,
            mlx_id=mlx5,
            desc=fake_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5}/node_desc", self.manifest_path
            ),
            fw_version=fake_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5}/fw_ver", self.manifest_path
            ),
            # fmt: off
            active=fake_read_sysfs_val(f"{sysfs_path}/infiniband/{mlx5}/ports/1/phys_state", self.manifest_path) == "5: LinkUp",
            # fmt: on
            link_state=fake_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5}/ports/1/state", self.manifest_path
            ),
            link_type=fake_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5}/ports/1/link_layer", self.manifest_path
            ),
            link_rate=fake_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5}/ports/1/rate", self.manifest_path
            ),
            operstate=fake_read_sysfs_val(
                f"{sysfs_path}/net/{ibdev}/operstate", self.manifest_path
            )
            == "up",
        )


def fake_read_sysfs_val(path: str, manifest_path: str) -> Optional[str]:
    data: Dict[str, Any] = {}

    with resources.open_text(health_checks, manifest_path) as contents:
        data = json.loads(contents.read())

    def read_value(path: str) -> Optional[str]:
        if path in data:
            return data[path].strip()
        else:
            return None

    return read_value(path)


def fake_list_sysfs_dir(path: str, manifest_path: str, default: List[str]) -> List[str]:
    data: Dict[str, Any] = {}

    with resources.open_text(health_checks, manifest_path) as contents:
        data = json.loads(contents.read())

    def read_dir(path: str, default: List[str]) -> List[str]:
        dirlist = []

        subfiles = list(filter(lambda x: x.startswith(path), data.keys()))

        for file in subfiles:
            path_len = len(path)
            subdir = file[path_len:].split("/")[1]
            if subdir != "" and subdir not in dirlist:
                dirlist.append(subdir)

        return default if not dirlist else dirlist

    return read_dir(path, default)


@pytest.fixture
def iblink_tester(request: pytest.FixtureRequest) -> FakeIBLinkCheckImpl:
    """Create FakeIBLinkCheckImpl object"""
    return FakeIBLinkCheckImpl(request.param)


@pytest.mark.parametrize(
    "iblink_tester, manifest_file, expected",
    [
        (
            "learn_good.json",
            "DGX_A100.json",
            (
                ExitCode.OK,
                "up: 8, down: 0",
            ),
        ),
        (
            "empty.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "up: 0, down: 8",
            ),
        ),
        (
            "learn_stuck_ib_intf.json",
            "DGX_A100.json",
            (
                ExitCode.WARN,
                "up: 6, down: 2",
            ),
        ),
        (
            "learn_ib_intf_bad_rate.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "up: 0, down: 8",
            ),
        ),
        (
            "learn_ib_misbound_if.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "MISBIND",
            ),
        ),
        (
            "learn_ib_intf_operstate_down.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "LINK_OPERSTATE_DOWN",
            ),
        ),
        (
            "learn_ib_intf_bad_version.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "FIRMWARE_MISMATCH",
            ),
        ),
    ],
    indirect=["iblink_tester"],
)
def test_check_iblink(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    iblink_tester: FakeIBLinkCheckImpl,
    manifest_file: str,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_iblink,
        f"fair_cluster prolog --log-folder={tmp_path} --manifest_file={manifest_file} --sink=do_nothing",
        obj=iblink_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


def test_iblinkissue_enum() -> None:
    last_criterion = 0
    for name, value in IBLinkIssue.__members__.items():
        if name.startswith("CRITERION"):
            last_criterion = value.value
            continue
        assert value.value > last_criterion
