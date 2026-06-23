# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Collection, Dict, List, Optional, Protocol

import click
from gcm.health_checks.check_utils.output_utils import CheckOutput
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.subprocess import shell_command
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from pydantic import BaseModel
from typeguard import typechecked

SHELL_CMD_TIMEOUT = 30


class EthDevice(BaseModel):
    netdev: str
    phys: Optional[bool] = None
    flags: List[str]
    speed: Optional[int] = None
    mtu: int


class EthManifest(BaseModel):
    devices: Dict[str, EthDevice]


class EthLinkCheck(CheckEnv, Protocol):
    def read_manifest(self, manifest_file: str) -> Dict[str, Any]: ...

    def query_netlink_stats(self) -> List[Dict[str, Any]]: ...

    def get_intf_ifcfg(self, ifname: str) -> Optional[Dict[str, str]]: ...

    def query_link_speed(self, ifname: str) -> Optional[str]: ...

    def query_link_phys_macaddr(self, ifname: str) -> Optional[Dict[str, str]]: ...


def check_cfg_macaddr(
    obj: EthLinkCheck,
    check: CheckOutput,
    node_manifest: Dict[str, Any],
) -> CheckOutput:
    """
    Checks that the on-disk configuration (/etc/sysconfig/network-scripts/ifcfg-$intf)
    can actually bind against the interfaces (via macaddr).

    Args:
        check: A check object passed in to be modified and returned
        node_manifest: A manifest file for the node in question
        netlink_info: Information about interfaces from _query_netlink_stats

    Returns:
        A check object updated with the results of the check if it fails, otherwise, return the original check.
    """
    eth_manifest = EthManifest(devices=node_manifest["eth"])
    for device, intf_spec in eth_manifest.devices.items():
        if intf_spec.phys is None or not intf_spec.phys:
            continue

        configs = obj.get_intf_ifcfg(intf_spec.netdev)
        macaddr = obj.query_link_phys_macaddr(intf_spec.netdev)

        if configs is None:
            check.short_out = f"Missing interface {device} ({intf_spec.netdev})!"
            check.check_status = ExitCode.CRITICAL
            return check

        if configs["HWADDR"].lower() != macaddr:
            check.long_out.append(
                f"{device} ({intf_spec.netdev}) has bad cfg (expect: {configs['HWADDR'].lower()}, actual: {macaddr})!"
            )
            check.check_status = ExitCode.CRITICAL
            check.short_out = "Mismatched interface/config mac addresses!"

    return check


def check_link_speed(
    obj: EthLinkCheck, check: CheckOutput, node_manifest: Dict[str, Any]
) -> CheckOutput:
    """
    Checks our links are at the speed we expect them to.

    Args:
        check: A check object passed in to be modified and returned
        node_manifest: A manifest file for the node in question

    Returns:
        A check object updated with the results of the check if it fails, otherwise, return the original check.
    """
    eth_manifest = EthManifest(devices=node_manifest["eth"])
    for device, intf_spec in eth_manifest.devices.items():
        if intf_spec.speed is None:
            continue

        expected = str(intf_spec.speed)
        linkspeed = obj.query_link_speed(intf_spec.netdev)

        if linkspeed != expected:
            check.check_status = ExitCode.WARN
            check.short_out = "Links are down-speed"
            check.long_out.append(
                f"{device} ({intf_spec.netdev}) is slower than expected ({linkspeed}Mbps vs {expected}Mbps)"
            )

    return check


def check_link_state(
    check: CheckOutput,
    node_manifest: Dict[str, Any],
    netlink_info: List[Dict[str, Any]],
) -> CheckOutput:
    """
    Checks that each link we track actually matches the state we would expect them to be in.
    This check first makes sure the operstate field is not "DOWN", and then checks that
    the flags on the interface (e.g. UP, LOWER_UP, SLAVE for bond legs) are all present.

    Args:
        check: A check object passed in to be modified and returned
        node_manifest: A manifest file for the node in question
        netlink_info: Information about interfaces from _query_netlink_stats

    Returns:
        A check object updated with the results of the check if it fails, otherwise, return the original check.
    """
    eth_manifest = EthManifest(devices=node_manifest["eth"])
    for device, intf_spec in eth_manifest.devices.items():
        # We can assume this is nonempty because _check_cfg_macaddr checks that we don't have missing netlink interfaces
        intf_state = list(
            filter(lambda x: x["ifname"] == intf_spec.netdev, netlink_info)
        )[0]

        if intf_state["operstate"] != "UP":
            check.check_status = ExitCode.CRITICAL
            check.long_out.append(f"{device} ({intf_spec.netdev}) is DOWN")

        missing_flags = [
            flag for flag in intf_spec.flags if flag not in intf_state["flags"]
        ]

        if len(missing_flags) > 0:
            check.check_status = ExitCode.CRITICAL
            check.long_out.append(
                f"{device} ({intf_spec.netdev}) has missing flag(s): {','.join(missing_flags)}"
            )

        if intf_state["mtu"] != intf_spec.mtu:
            if check.check_status != ExitCode.CRITICAL:
                check.check_status = ExitCode.WARN
            check.long_out.append(
                f"{device} ({intf_spec.netdev}) has bad mtu ({intf_state['mtu']} < {intf_spec.mtu})"
            )

    if check.check_status != ExitCode.OK:
        check.short_out = "Interfaces in bad states"

    return check


def process_ethlink(obj: EthLinkCheck, node_manifest: Dict[str, Any]) -> CheckOutput:
    if "eth" not in node_manifest:
        return CheckOutput(
            "check_ethlink",
            check_status=ExitCode.OK,
            short_out="No ethernet interface in manifest, skipping",
        )

    out = CheckOutput(
        "check_ethlink",
        check_status=ExitCode.OK,
    )

    netlink_info = obj.query_netlink_stats()
    out = check_cfg_macaddr(obj, out, node_manifest)
    if out.check_status != ExitCode.OK:
        return out

    out = check_link_state(out, node_manifest, netlink_info)
    if out.check_status != ExitCode.OK:
        return out

    out = check_link_speed(obj, out, node_manifest)
    if out.check_status != ExitCode.OK:
        return out

    return out


@dataclass
class EthLinkCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def read_manifest(self, manifest_file: str) -> Dict[str, Any]:
        with open(manifest_file) as manifest:
            return json.loads(manifest.read())

    def query_netlink_stats(self) -> List[Dict[str, Any]]:
        """
        Asks netlink via ip to grab all interfaces and parse into a list object.
        Returns:
            The state of all interfaces according to netlink
        """
        ip_out = shell_command("/usr/sbin/ip -j addr", SHELL_CMD_TIMEOUT)
        return json.loads(ip_out.stdout)

    def get_intf_ifcfg(self, ifname: str) -> Optional[Dict[str, str]]:
        """
        Fetches a dictionary of values associated with the /etc/sysconfig/network-scripts/ifcfg-*
        or nmcli configuration values for a specific interface.

        If none exists, return None instead.

        Args:
            ifname: The netlink interface name

        Returns:
            A dictionary of options and their values (stringly typed) if the configuration exists,
            None otherwise.
        """
        if os.path.exists(f"/etc/sysconfig/network-scripts/ifcfg-{ifname}"):
            with open(f"/etc/sysconfig/network-scripts/ifcfg-{ifname}", "r") as file:
                lines = file.read().strip().split("\n")
                return {
                    field[0]: field[1] for field in map(lambda x: x.split("="), lines)
                }
        return self._get_intf_ifcfg_from_nmcli(ifname)

    @staticmethod
    def _get_intf_ifcfg_from_nmcli(ifname: str) -> Optional[Dict[str, str]]:
        """
        CentOS 10+ fallback: synthesize an ifcfg-equivalent dict from nmcli when
        /etc/sysconfig/network-scripts/ifcfg-* is unavailable (ifcfg-rh plugin
        is dropped on CentOS 10).
        """
        device_fields = [
            "GENERAL.HWADDR",
            "GENERAL.DEVICE",
            "GENERAL.TYPE",
            "GENERAL.MTU",
            "GENERAL.STATE",
            "GENERAL.CONNECTION",
        ]
        try:
            device_out = subprocess.check_output(
                [
                    "nmcli",
                    "-t",
                    "-e",
                    "no",
                    "-f",
                    ",".join(device_fields),
                    "device",
                    "show",
                    ifname,
                ],
                stderr=subprocess.DEVNULL,
                timeout=30,
            ).decode()
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            return None

        device_props: Dict[str, str] = {}
        for line in device_out.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                device_props[key.strip()] = value.strip()

        if not device_props.get("GENERAL.HWADDR"):
            return None

        nmcli_type = device_props.get("GENERAL.TYPE", "")
        # nmcli prints "--" for an unmanaged/inactive connection; treat it as empty.
        connection = device_props.get("GENERAL.CONNECTION", "")
        if connection == "--":
            connection = ""
        return {
            "HWADDR": device_props["GENERAL.HWADDR"],
            "DEVICE": device_props.get("GENERAL.DEVICE", ifname),
            "NAME": connection or ifname,
            "TYPE": nmcli_type.capitalize() if nmcli_type else "",
            "MTU": device_props.get("GENERAL.MTU", ""),
            "STATE": device_props.get("GENERAL.STATE", ""),
        }

    def query_link_speed(self, ifname: str) -> Optional[str]:
        """
        Reads the link speed (in Mbps) of an interface from sysfs

        Args:
            ifname: Netlink interface name

        Returns:
            The speed that the kernel reports from the interface, in Mbps
        """
        if os.path.exists(f"/sys/class/net/{ifname}/speed"):
            with open(f"/sys/class/net/{ifname}/speed", "r") as file:
                value = file.read().strip()
                return value
        else:
            return None

    def query_link_phys_macaddr(self, ifname: str) -> Optional[Dict[str, str]]:
        """
        Queries ethtool -P $ifname to fetch the permanent/physical mac address of a netlink interface.
        This needed is because kernel will report the bond mac for all legs of a bond via ip and sysfs,
        and /sys/class/net will not report physical mac addresses, only the phys driver will.

        Args:
            ifname: The netlink interface name

        Returns:
            The mac address of the interface in question, in lowercase :-separated octet form.
            If the intf doesn't exist, it returns "No such device" instead.
        """
        cmd = f"/usr/sbin/ethtool -P {ifname}"
        cmd_out = shell_command(cmd, SHELL_CMD_TIMEOUT)
        if cmd_out.returncode == 0 and cmd_out.stdout is not None:
            return cmd_out.stdout.strip().split(":", 1)[1].strip()
        else:
            return None


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option("--manifest_file", default="/etc/manifest.json")
@click.pass_obj
@typechecked
def check_ethlink(
    obj: Optional[EthLinkCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    manifest_file: str,
) -> None:
    """Check eth links against the manifest file"""
    if obj is None:
        obj = EthLinkCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_ETHLINK,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ethlink(),
    ) as rt:
        node_manifest: Dict[str, Any] = {}
        try:
            node_manifest = obj.read_manifest(manifest_file)
            check = process_ethlink(obj, node_manifest)
            exit_code, msg = check.check_status, str(check)
        except Exception as e:
            exit_code = ExitCode.WARN
            msg = f"Exception occured: {e}"

        rt.finish(exit_code, msg)
