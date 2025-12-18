# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
import os
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from enum import auto, Enum
from typing import Any, Collection, Dict, List, NamedTuple, Optional, Protocol, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.output_utils import CheckOutput
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.checks.check_pci import PciDevice, PciManifest
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from pydantic import BaseModel
from typeguard import typechecked


class IBLinkIssue(Enum):
    MISBIND = auto()  # physical slot is bound to incorrect/invalid ib logical device
    MLX5_MISMATCH = auto()  # ib netdev and mlx5 logical device doesn't match
    MLX5_PROTOCOL_MISMATCH = auto()  # the port is not in InfiniBand mode
    LINK_RATE_MISMATCH = auto()  # ib/mlx5 device reports the right speed
    LINK_NOT_UP = auto()  # The link is not LinkUp e.g. Physically disconnected
    LINK_BAD_STATE = auto()  # The link is LinkUp but state is not 'ACTIVE'
    LINK_OPERSTATE_DOWN = auto()

    CRITERION_NOT_CRITICAL = (
        100  # All issues with ID > CRITERION_NOT_CRITICAL are not critical
    )

    LINK_IN_INIT = (
        auto()
    )  # The link is in an init state - it's a 'softer' failure that may resolve when the card links up to the subnet manager
    FIRMWARE_MISMATCH = auto()  # node's firmware doesn't match

    CRITERION_NOT_WARNING = (
        200  # All issues with ID > CRITERION_NOT_WARNING are not warnings
    )

    CRITERION_OK = 1000


class IBLinkState(NamedTuple):
    slot_id: str
    pci_id: str
    ib_id: str
    mlx_id: str
    desc: Optional[str] = None
    fw_version: Optional[str] = None
    active: Optional[bool] = None
    link_state: Optional[str] = None
    link_type: Optional[str] = None
    link_rate: Optional[str] = None
    operstate: Optional[bool] = None


class IBInterface(BaseModel):
    mlx: str
    desc: str


class IBManifest(BaseModel):
    link_rate: str
    firmware_version: List[str]
    interfaces: Dict[str, IBInterface]


class IBLinkCheck(CheckEnv, Protocol):
    def read_manifest(self, manifest_file: str) -> Dict[str, Any]: ...

    def read_cardstate(self, pci_id: str, pci_info: PciDevice) -> IBLinkState: ...


@dataclass
class IBLinkCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def read_manifest(self, manifest_file: str) -> Dict[str, Any]:
        with open(manifest_file) as manifest:
            return json.loads(manifest.read())

    def read_cardstate(self, pci_id: str, pci_info: PciDevice) -> IBLinkState:
        """
        Reads a card's state from /sys or prefix/sys (For testing).
        Since we have 1:1 mapping of HCA pci-ids (including subfunctions) to link interfaces, cardstate maps uniformly to linkstate.
        """
        sysfs_path = os.path.join("/sys/bus/pci/devices", pci_id)

        mlx5 = _list_sysfs_dir(f"{sysfs_path}/infiniband")
        ibdev = _list_sysfs_dir(f"{sysfs_path}/net")
        if mlx5 is None:
            mlx5_str = "UNKNOWN"
        else:
            mlx5_str = mlx5[0]
        if ibdev is None:
            ibdev_str = "UNKNOWN"
        else:
            ibdev_str = ibdev[0]

        return IBLinkState(
            slot_id=pci_info.slot,
            pci_id=pci_id,
            ib_id=ibdev_str,
            mlx_id=mlx5_str,
            desc=_read_sysfs_val(f"{sysfs_path}/infiniband/{mlx5_str}/node_desc"),
            fw_version=_read_sysfs_val(f"{sysfs_path}/infiniband/{mlx5_str}/fw_ver"),
            # fmt: off
            active=_read_sysfs_val(f"{sysfs_path}/infiniband/{mlx5_str}/ports/1/phys_state") == "5: LinkUp",
            # fmt: on
            link_state=_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5_str}/ports/1/state"
            ),
            link_type=_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5_str}/ports/1/link_layer"
            ),
            link_rate=_read_sysfs_val(
                f"{sysfs_path}/infiniband/{mlx5_str}/ports/1/rate"
            ),
            operstate=_read_sysfs_val(f"{sysfs_path}/net/{ibdev_str}/operstate")
            == "up",
        )


# Helper functions to do read-and-return-value-if-fail
def _read_sysfs_val(path: str) -> Optional[str]:
    try:
        with open(path, "r") as file:
            value = file.read().strip()
            return value
    except Exception:
        logging.getLogger(__name__).exception("_read_sysfs_val: an exception occurred")
        return None


def _list_sysfs_dir(path: str) -> Optional[List[str]]:
    try:
        return os.listdir(path)
    except Exception:
        logging.getLogger(__name__).exception("_read_sysfs_val: an exception occurred")
        return None


def validate_ib(
    link_state: IBLinkState, manifest: Dict[str, Any]
) -> List[Tuple[IBLinkIssue, str]]:
    """
    validate_ib takes the link state of a card and returns a list of tuples of error codes + a short string of each issue
    Parameters:
        link_state: The link state as read by read_cardstate
        manifest: The manifest as given by manifest.load, which gives us what the node looks like
    Returns:
        List[Tuple[IBLinkIssue, String]], a list of error codes and values
    """
    pci_manifest = PciManifest(devices=manifest["pci"])
    ibnetdev = link_state.ib_id
    mlxdev = link_state.mlx_id
    pci_spec = pci_manifest.devices[link_state.pci_id]
    dev_slot = pci_spec.slot
    # Confirm that all mappings are correct, we have to give up if not since further reads might as well just be garbage
    # The endswith is due to pci spec's dev member being defined by full sysfs/devfs path and not by logical id
    if not pci_manifest.devices[link_state.pci_id].dev.endswith(ibnetdev):
        return [
            (
                IBLinkIssue.MISBIND,
                f"{dev_slot} is bound to {ibnetdev}, expected {pci_spec.dev}",
            )
        ]
    link_issues: List[Tuple[IBLinkIssue, str]] = []
    ib_manifest = IBManifest(**manifest["ib"])
    ibintf_spec = ib_manifest.interfaces[ibnetdev]

    # Is the mlx5 logical device the same as expected? (Should never happen, but maybe it does?)
    if ibintf_spec.mlx != mlxdev:
        link_issues.append(
            (
                IBLinkIssue.MLX5_MISMATCH,
                f"{dev_slot}({ibnetdev}) is bound to {mlxdev}, expected {ibintf_spec.mlx}",
            )
        )
    # Is the firmware at the expected version
    if link_state.fw_version not in ib_manifest.firmware_version:
        link_issues.append(
            (
                IBLinkIssue.FIRMWARE_MISMATCH,
                f"{dev_slot}({ibnetdev}) has fw version {link_state.fw_version}, expected [{','.join(manifest['ib']['firmware_version'])}]",
            )
        )
    # Is the MLX5 device *properly* infiniband (should present as ibdev bind names, but double checking doesn't hurt)?
    if link_state.link_type != "InfiniBand":
        link_issues.append(
            (
                IBLinkIssue.MLX5_PROTOCOL_MISMATCH,
                f"{dev_slot}({ibnetdev}) is not presenting as an InfiniBand link!",
            )
        )
    # If the link is not active, then the port is down
    if not link_state.active:
        link_issues.append(
            (
                IBLinkIssue.LINK_NOT_UP,
                f"{dev_slot}({ibnetdev}) is not up, link state is {link_state.link_state}",
            )
        )
    if link_state.link_state != "4: ACTIVE":
        link_issues.append(
            (
                (
                    IBLinkIssue.LINK_IN_INIT
                    if link_state.link_state == "2: INIT"
                    else IBLinkIssue.LINK_BAD_STATE
                ),
                f"{dev_slot}({ibnetdev}) is not up, link state is {link_state.link_state}",
            )
        )
    # Is the link at the right speed if it is active?
    if link_state.active and link_state.link_rate != ib_manifest.link_rate:
        link_issues.append(
            (
                IBLinkIssue.LINK_RATE_MISMATCH,
                f"{dev_slot}({ibnetdev}) has degraded link {link_state.link_rate}",
            )
        )
    # This link is *weird*, netlink operstate is down, but IB operstate may be up?
    if link_state.link_state == "4: ACTIVE" and not link_state.operstate:
        link_issues.append(
            (
                IBLinkIssue.LINK_OPERSTATE_DOWN,
                f"{dev_slot}({ibnetdev}) is ACTIVE, but the logical interface is down(?!)",
            )
        )
    return link_issues


def process_iblink(obj: IBLinkCheck, monitored_devices: Dict[str, Any]) -> CheckOutput:
    check = CheckOutput("check_iblink")

    def format_issues(per_card_issues: List[Tuple[IBLinkIssue, str]]) -> str:
        return "; ".join(
            [f"{issue[0].name}: {issue[1]}".strip() for issue in per_card_issues]
        )

    pci_manifest = PciManifest(devices=monitored_devices["pci"])
    cards: List[IBLinkState] = []
    for pci_dev, dev_info in pci_manifest.devices.items():
        if dev_info.type == "ib":
            cards.append(obj.read_cardstate(pci_dev, dev_info))

    good_cards = 0

    validation = list(map(lambda x: validate_ib(x, monitored_devices), cards))
    issue_messages = list(map(lambda x: format_issues(x), validation))
    for bad_result in validation:
        if not bad_result:
            good_cards += 1

    flatten_issues = [link_issue for card in validation for link_issue in card]

    lowest_issue = (
        min(map(lambda x: x[0].value, flatten_issues))
        if flatten_issues
        else IBLinkIssue.CRITERION_OK.value
    )  # Extract the lowest numerical value IBLinkIssue enum from all interface issues for status

    check.check_status = ExitCode.CRITICAL
    if lowest_issue > IBLinkIssue.CRITERION_NOT_CRITICAL.value:
        check.check_status = ExitCode.WARN
    if lowest_issue > IBLinkIssue.CRITERION_NOT_WARNING.value:
        check.check_status = ExitCode.OK

    check.short_out = f"up: {good_cards}, down: {len(cards) - good_cards}"

    for issue_msg in issue_messages:
        if issue_msg != "":
            check.long_out.append(issue_msg)

    return check


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option("--manifest_file", default="/etc/manifest.json")
@click.pass_obj
@typechecked
def check_iblink(
    obj: Optional[IBLinkCheck],
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
    """Check IB links of the system against the manifest file"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check-iblink: cluster: {cluster}, node: {node}, type: {type} manifest file: {manifest_file}"
    )
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")

    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )

    if obj is None:
        obj = IBLinkCheckImpl(cluster, type, log_level, log_folder)

    exit_code = ExitCode.UNKNOWN
    msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.CHECK_IBLINK.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_IBLINK,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_iblink():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_IBLINK.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        node_manifest: Dict[str, Any] = {}
        try:
            node_manifest = obj.read_manifest(manifest_file)
            check = process_iblink(obj, node_manifest)
            exit_code, msg = check.check_status, str(check)
        except Exception as e:
            exit_code = ExitCode.WARN
            msg = f"Unable to open manifest file {manifest_file}, {e}"

        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)
