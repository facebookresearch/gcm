# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
import subprocess
from dataclasses import dataclass, field
from importlib import import_module, resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_ethlink import check_ethlink, EthLinkCheckImpl
from gcm.health_checks.types import ExitCode
from gcm.tests.data import health_checks

# Resolve the module via sys.modules (import_module) rather than `import … as`,
# because `gcm.health_checks.checks.__init__` rebinds the `check_ethlink`
# attribute on the package to the Click Command of the same name. `import … as`
# does a getattr-style lookup at the end and would yield the Command, not the
# module.
_ethlink_mod = import_module("gcm.health_checks.checks.check_ethlink")


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


SAMPLE_NMCLI_DEVICE_OUTPUT = (
    "GENERAL.HWADDR:10:70:FD:88:B7:D0\n"
    "GENERAL.DEVICE:enp161s0\n"
    "GENERAL.TYPE:ethernet\n"
    "GENERAL.MTU:9192\n"
    "GENERAL.STATE:100 (connected)\n"
    "GENERAL.CONNECTION:enp161s0\n"
)


def _nmcli_side_effect(
    device_out: Optional[bytes] = None,
    connection_out: Optional[bytes] = None,
    device_side_effect: Optional[BaseException] = None,
    connection_side_effect: Optional[BaseException] = None,
) -> Any:
    """
    Build a check_output side_effect that routes based on whether the argv
    contains `device show` (returns/raises device_*) or `connection show`
    (returns/raises connection_*).
    """

    def _impl(argv: List[str], *args: Any, **kwargs: Any) -> bytes:
        if "device" in argv and "show" in argv:
            if device_side_effect is not None:
                raise device_side_effect
            assert device_out is not None
            return device_out
        if "connection" in argv and "show" in argv:
            if connection_side_effect is not None:
                raise connection_side_effect
            assert connection_out is not None
            return connection_out
        raise AssertionError(f"unexpected nmcli invocation: {argv!r}")

    return _impl


def test_nmcli_fallback_happy_path() -> None:
    connection_out = "802-3-ethernet.mac-address:10:70:FD:88:B7:D0\n".encode()
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=_nmcli_side_effect(
            device_out=SAMPLE_NMCLI_DEVICE_OUTPUT.encode(),
            connection_out=connection_out,
        ),
    ):
        result = EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0")
    assert result == {
        "HWADDR": "10:70:FD:88:B7:D0",
        "DEVICE": "enp161s0",
        "NAME": "enp161s0",
        "TYPE": "Ethernet",
        "MTU": "9192",
        "STATE": "100 (connected)",
    }


def test_nmcli_fallback_invokes_subprocess_with_timeout() -> None:
    connection_out = "802-3-ethernet.mac-address:10:70:FD:88:B7:D0\n".encode()
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=_nmcli_side_effect(
            device_out=SAMPLE_NMCLI_DEVICE_OUTPUT.encode(),
            connection_out=connection_out,
        ),
    ) as mock_check_output:
        EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0")
    calls = mock_check_output.call_args_list
    assert len(calls) == 2
    device_args, device_kwargs = calls[0]
    assert device_args[0][0] == "nmcli"
    assert device_args[0][-3:] == ["device", "show", "enp161s0"]
    assert device_kwargs["timeout"] == 30
    assert device_kwargs["stderr"] == subprocess.DEVNULL
    conn_args, conn_kwargs = calls[1]
    assert conn_args[0][0] == "nmcli"
    assert conn_args[0][-3:] == ["connection", "show", "enp161s0"]
    assert "802-3-ethernet.mac-address" in conn_args[0]
    assert conn_kwargs["timeout"] == 30
    assert conn_kwargs["stderr"] == subprocess.DEVNULL


def test_nmcli_fallback_bond_slave_uses_connection_binding_mac() -> None:
    """
    On a bond slave, `nmcli device show` reports the bond-inherited MAC as
    GENERAL.HWADDR, but the connection profile's 802-3-ethernet.mac-address
    still holds the real permanent NIC MAC. The check must compare against
    the binding MAC so bond slaves do not spuriously fail.
    """
    device_out = (
        "GENERAL.HWADDR:FA:CE:B0:0C:19:83\n"  # bond master's cloned MAC
        "GENERAL.DEVICE:enp97s0f0np0\n"
        "GENERAL.TYPE:ethernet\n"
        "GENERAL.MTU:9192\n"
        "GENERAL.STATE:100 (connected)\n"
        "GENERAL.CONNECTION:enp97s0f0np0\n"
    ).encode()
    connection_out = "802-3-ethernet.mac-address:10:70:FD:BD:7D:5C\n".encode()
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=_nmcli_side_effect(
            device_out=device_out,
            connection_out=connection_out,
        ),
    ):
        result = EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp97s0f0np0")
    assert result is not None
    assert result["HWADDR"] == "10:70:FD:BD:7D:5C"


def test_nmcli_fallback_connection_missing_binding_mac_falls_back_to_device() -> None:
    connection_out = "802-3-ethernet.mac-address:\n".encode()
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=_nmcli_side_effect(
            device_out=SAMPLE_NMCLI_DEVICE_OUTPUT.encode(),
            connection_out=connection_out,
        ),
    ):
        result = EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0")
    assert result is not None
    assert result["HWADDR"] == "10:70:FD:88:B7:D0"


def test_nmcli_fallback_connection_show_fails_falls_back_to_device() -> None:
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=_nmcli_side_effect(
            device_out=SAMPLE_NMCLI_DEVICE_OUTPUT.encode(),
            connection_side_effect=subprocess.CalledProcessError(
                returncode=10, cmd="nmcli"
            ),
        ),
    ):
        result = EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0")
    assert result is not None
    assert result["HWADDR"] == "10:70:FD:88:B7:D0"


def test_nmcli_fallback_connection_returns_placeholder_falls_back() -> None:
    connection_out = "802-3-ethernet.mac-address:--\n".encode()
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=_nmcli_side_effect(
            device_out=SAMPLE_NMCLI_DEVICE_OUTPUT.encode(),
            connection_out=connection_out,
        ),
    ):
        result = EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0")
    assert result is not None
    assert result["HWADDR"] == "10:70:FD:88:B7:D0"


def test_nmcli_fallback_missing_hwaddr_returns_none() -> None:
    output = "GENERAL.HWADDR:\nGENERAL.DEVICE:enp161s0\nGENERAL.TYPE:ethernet\n"
    with patch.object(_ethlink_mod, "check_output", return_value=output.encode()):
        assert EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0") is None


def test_nmcli_fallback_command_not_found_returns_none() -> None:
    with patch.object(_ethlink_mod, "check_output", side_effect=FileNotFoundError()):
        assert EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0") is None


def test_nmcli_fallback_command_fails_returns_none() -> None:
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=subprocess.CalledProcessError(returncode=1, cmd="nmcli"),
    ):
        assert EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0") is None


def test_nmcli_fallback_command_times_out_returns_none() -> None:
    with patch.object(
        _ethlink_mod,
        "check_output",
        side_effect=subprocess.TimeoutExpired(cmd="nmcli", timeout=30),
    ):
        assert EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("enp161s0") is None


@pytest.mark.parametrize("connection_value", ["--", ""])
def test_nmcli_fallback_unmanaged_connection_falls_back_to_ifname(
    connection_value: str,
) -> None:
    output = (
        "GENERAL.HWADDR:AA:BB:CC:DD:EE:FF\n"
        "GENERAL.DEVICE:eth0\n"
        "GENERAL.TYPE:ethernet\n"
        "GENERAL.MTU:1500\n"
        "GENERAL.STATE:30 (disconnected)\n"
        f"GENERAL.CONNECTION:{connection_value}\n"
    )
    # With no active connection name, we cannot look up a connection profile,
    # so HWADDR must fall back to GENERAL.HWADDR — check_output should be
    # called exactly once (device show only, no connection show).
    with patch.object(
        _ethlink_mod, "check_output", return_value=output.encode()
    ) as mock_check_output:
        result = EthLinkCheckImpl._get_intf_ifcfg_from_nmcli("eth0")
    assert result == {
        "HWADDR": "AA:BB:CC:DD:EE:FF",
        "DEVICE": "eth0",
        "NAME": "eth0",
        "TYPE": "Ethernet",
        "MTU": "1500",
        "STATE": "30 (disconnected)",
    }
    assert mock_check_output.call_count == 1
