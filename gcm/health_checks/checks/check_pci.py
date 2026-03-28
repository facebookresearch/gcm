# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Check PCI devices against manifest file."""

import json
import logging
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, Optional, Protocol

import click
from gcm.health_checks.check_utils.output_utils import CheckOutput, Metric
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from pydantic import BaseModel
from typeguard import typechecked


class PciLink(NamedTuple):
    """A PCI device as read from the `/sys` filesystem."""

    pci_slot: str
    link_speed: Optional[str]
    link_width: Optional[int]

    @property
    def link_exists(self) -> bool:
        """Determine whether the link speed and width both exist."""
        return self.link_speed is not None and self.link_width is not None


class PciCheck(CheckEnv, Protocol):
    """Protocol for implementation or testing."""

    def read_pci_link(self, pci_slot: str) -> PciLink:
        """Generate a `PciLink` object for a particular PCI slot."""

    def read_manifest(self, manifest_file: str) -> dict[str, Any]:
        """Return a parsed version of the `/etc/manifest.json` file."""


class PciDevice(BaseModel):
    """A PCI device as read from the `/etc/manifest.json` file."""

    type: Optional[str] = None
    dev: str
    zone: str
    slot: str
    link_speed: Optional[list[str]] = None
    link_width: int
    topology_critical: Optional[bool] = None


class PciManifest(BaseModel):
    """The "pci" portion of the parsed `/etc/manifest.json` file."""

    devices: dict[str, PciDevice]


@dataclass
class PciCheckImpl:
    """The check-pci health_check implementation."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def read_pci_link(self, pci_slot: str) -> PciLink:
        """Return an object created from a `/sys' filesystem entry."""
        pci_slot_data = pci_slot.split(":")
        pci_slot_key = ":".join(pci_slot_data[0:2])
        sysfs_device_path = (
            Path("/sys/class/pci_bus") / pci_slot_key / "device" / pci_slot
        )
        sysfs_device_link_speed_path = sysfs_device_path / "current_link_speed"
        sysfs_device_link_width_path = sysfs_device_path / "current_link_width"
        sysfs_link_speed = _read_sysfs_val(sysfs_device_link_speed_path) or None
        sysfs_link_width = _read_sysfs_val(sysfs_device_link_width_path) or None
        sysfs_link_width_int = int(sysfs_link_width) if sysfs_link_width else None
        return PciLink(pci_slot, sysfs_link_speed, sysfs_link_width_int)

    def read_manifest(self, manifest_file: str) -> dict[str, Any]:
        """Parse the manifest_file as JSON and return a dict."""
        return json.loads(Path(manifest_file).read_text(encoding="utf-8"))


def _read_sysfs_val(path: Path) -> Optional[str]:
    """Read the value stored in a `/sys` filesystem path."""
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def check_pci_state(
    obj: PciCheck, monitored_devices: PciManifest, logger: logging.Logger
) -> CheckOutput:
    """Compare actual PCI device with expected values from manifest."""
    check = CheckOutput("check_pci")
    passing_counter = 0
    missing_counter = 0
    degraded_counter = 0

    pci_dev_links = [obj.read_pci_link(x) for x in monitored_devices.devices]

    for link in pci_dev_links:
        slot = link.pci_slot
        device = monitored_devices.devices[slot]
        name = device.slot
        logger.debug(f"Checking status of PCI device {slot}")
        logger.debug(f"manifest = {device}")
        logger.debug(f"slot {slot}: x{link.link_width} @ {link.link_speed}")
        if not link.link_exists:
            check.check_status = ExitCode.CRITICAL
            msg = f"{name} is not present at {slot}."
            logger.debug(msg)
            check.long_out.append(msg)
            missing_counter += 1

            # If the device in the manifest is tagged as invalidating topology
            # (e.g. renumbering/ordering devices if it's not present)
            # we can't go much further, so we have to stop here.
            if device.topology_critical:
                break
        else:
            logger.debug(f"{name} is present at {slot}.")
            expected_speed = device.link_speed or [""]
            if (
                link.link_width != device.link_width
                or link.link_speed not in expected_speed
            ):

                check.check_status = ExitCode.CRITICAL
                msg = (
                    f"{name} has degraded PCIe link "
                    f"(current: 'x{link.link_width} @ {link.link_speed}', "
                    f"expected: 'x{device.link_width} @ {'|'.join(expected_speed)}')."
                )
                logger.debug(msg)
                check.long_out.append(msg)
                degraded_counter += 1

            else:
                passing_counter += 1

    device_count = len(pci_dev_links)
    if passing_counter == device_count:
        check.check_status = ExitCode.OK
        check.short_out = "PCIe Devices Good"
        check.short_metrics = [
            Metric("pass", passing_counter, metric_max=str(device_count)),
        ]
    else:
        check.check_status = ExitCode.CRITICAL
        check.short_out = "PCIe Issues Detected"
        check.short_metrics = [
            Metric("pass", passing_counter, metric_max=str(device_count)),
            Metric("missing", missing_counter, metric_max=str(device_count)),
            Metric("degraded", degraded_counter, metric_max=str(device_count)),
            Metric(
                "unknown",
                device_count - (passing_counter + degraded_counter + missing_counter),
                metric_max=str(device_count),
            ),
        ]
    logger.debug(check.short_out)
    for metric in check.short_metrics:
        logger.debug(metric)
    return check


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option("--manifest_file", default="/etc/manifest.json")
@click.pass_obj
@typechecked
def check_pci(
    obj: Optional[PciCheck],
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
    """Check pci subsystem against the manifest file."""
    if obj is None:
        obj = PciCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_PCI,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_pci(),
    ) as rt:
        node_manifest: dict[str, Any] = {}
        try:
            node_manifest = obj.read_manifest(manifest_file)
            pci_manifest_data = node_manifest["pci"]
            pci_manifest = PciManifest(devices=pci_manifest_data)
            check = check_pci_state(obj, pci_manifest, rt.logger)
            exit_code, msg = check.check_status, str(check)
        except Exception as e:
            exit_code = ExitCode.WARN
            msg = f"Exception occurred: {e}"

        rt.finish(exit_code, msg)
