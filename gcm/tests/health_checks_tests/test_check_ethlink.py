# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ethlink import check_ethlink
from gcm.health_checks.types import ExitCode
from gcm.tests.data import health_checks


@dataclass
class FakeEthLinkCheckImpl:
    manifest_path: str

    data: Dict[str, Any] = field(default_factory=dict)
    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def __post_init__(self) -> None:
        with resources.open_text(health_checks, self.manifest_path) as contents:
            self.data = json.loads(contents.read())

    def read_manifest(self, manifest_file: str) -> Dict[str, Any]:
        with resources.open_text(health_checks, manifest_file) as manifest:
            return json.loads(manifest.read())

    def query_netlink_stats(self) -> List[Dict[str, Any]]:
        return self.data["intf_status"]

    def get_intf_ifcfg(self, ifname: str) -> Optional[Dict[str, str]]:
        return self.data["intf_ifcfg"][ifname]

    def query_link_speed(self, ifname: str) -> Optional[str]:
        return self.data["link_speed"][ifname]

    def query_link_phys_macaddr(self, ifname: str) -> Optional[Dict[str, str]]:
        return self.data["phys_macaddr"][ifname]


@pytest.fixture
def ethlink_tester(request: pytest.FixtureRequest) -> FakeEthLinkCheckImpl:
    """Create FakeEthLinkCheckImpl object"""
    return FakeEthLinkCheckImpl(request.param)


@pytest.mark.parametrize(
    "ethlink_tester, manifest_file, expected",
    [
        (
            "eth_learn_good.json",
            "DGX_A100.json",
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            "empty.json",
            "empty.json",
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            "eth_learn_nic_swap.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "has bad cfg",
            ),
        ),
        (
            "eth_learn_missing_intf.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "Missing interface PCIE_4",
            ),
        ),
        (
            "eth_learn_down_intf.json",
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "is DOWN",
            ),
        ),
        (
            "eth_learn_mtu_bad.json",
            "DGX_A100.json",
            (
                ExitCode.WARN,
                "has bad mtu",
            ),
        ),
        (
            "eth_learn_degraded_intf.json",
            "DGX_A100.json",
            (
                ExitCode.WARN,
                "is slower than expected (200000Mbps vs 400000Mbps)",
            ),
        ),
    ],
    indirect=["ethlink_tester"],
)
def test_check_ethlink(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ethlink_tester: FakeEthLinkCheckImpl,
    manifest_file: str,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ethlink,
        f"fair_cluster prolog --log-folder={tmp_path} --manifest_file={manifest_file} --sink=do_nothing",
        obj=ethlink_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
