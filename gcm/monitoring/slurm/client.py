# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import csv
import json
import logging
import re
import subprocess
from dataclasses import fields
from typing import (
    Any,
    Callable,
    Generator,
    Hashable,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    TYPE_CHECKING,
)

import clusterscope

from gcm.monitoring.dataclass_utils import instantiate_dataclass
from gcm.monitoring.slurm.constants import PENDING_RESOURCE_REASONS, SLURM_CLI_DELIMITER

from gcm.monitoring.slurm.sacct import get_sacct_lines
from gcm.monitoring.utils.shell import _gen_lines, _popen

from gcm.schemas.slurm.sdiag import Sdiag
from gcm.schemas.slurm.sinfo import Sinfo
from gcm.schemas.slurm.sinfo_node import SinfoNode
from gcm.schemas.slurm.sinfo_row import SinfoRow
from gcm.schemas.slurm.squeue import JOB_DATA_SLURM_FIELDS, JobData

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

logger = logging.getLogger(__name__)


def add_pending_resources(message: dict[Any, Any]) -> None:
    """Adds an additional field ("PENDING_RESOURCES") to squeue output that tracks if the job is ready to be scheduled and waiting for resources."""
    if message["STATE"] == "PENDING" and message["REASON"] in PENDING_RESOURCE_REASONS:
        message["PENDING_RESOURCES"] = "True"
    else:
        message["PENDING_RESOURCES"] = "False"


class SlurmClient(Protocol):
    """A low-level Slurm client."""

    def squeue(
        self,
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Iterable[DataclassInstance]:
        """Get lines of queue information. Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.

        If an error occurs during execution, RuntimeError should be raised.
        """

    def sinfo(self) -> Iterable[str]:
        """Get lines of node information. Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.

        If an error occurs during execution, RuntimeError should be raised.
        """

    def sdiag_structured(self) -> Sdiag:
        """Get lines of node information. Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.

        If an error occurs during execution, RuntimeError should be raised.
        """

    def sinfo_structured(self) -> Sinfo:
        """Get Slurm node information in a structured format."""

    def sacctmgr_qos(self) -> Iterable[str]:
        """Get lines of qos information. Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.

        If an error occurs during execution, RuntimeError should be raised.
        """

    def sacctmgr_user(self) -> Iterable[str]:
        """Get lines of user information. Each line should be pipe separated.
        Lines should not have a trailing newline.
        If an error occurs during execution, RuntimeError should be raised.
        """

    def sacctmgr_user_info(self, username: str) -> Iterable[str]:
        """Get lines of detailed user information. Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.
        If an error occurs during execution, RuntimeError should be raised.
        """

    def sacct_running(self) -> Generator[str, None, None]:
        """Get lines of sacct output from running jobs only (state=running,r).
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.

        If an error occurs during execution, RuntimeError should be raised.
        """

    def scontrol_partition(self) -> Iterable[str]:
        """Get lines of scontrol partition information."""

    def scontrol_config(self) -> Iterable[str]:
        """Get lines of scontrol config information."""

    def count_runaway_jobs(self) -> int:
        """Return the count of runaway jobs"""


class SlurmCliClient(SlurmClient):
    def __init__(
        self,
        *,
        popen: Callable[[List[str]], "subprocess.Popen[str]"] = _popen,
    ):
        self.__popen = popen

    def _parse_squeue(
        self,
        gen_squeue_lines: Iterable[str],
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Iterable[DataclassInstance]:
        for line in gen_squeue_lines:
            row: dict[Hashable, Any] = {}
            slurm_row = line.split(SLURM_CLI_DELIMITER)
            for k, v in zip(JOB_DATA_SLURM_FIELDS, slurm_row):
                row[k] = v
            row.update(attributes or {})
            add_pending_resources(row)
            row["derived_cluster"] = derived_cluster_fetcher(row)
            yield instantiate_dataclass(JobData, row, logger=logger)

    def squeue(
        self,
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Iterable[DataclassInstance]:
        formatted_fields = [
            f"{field.upper()}:{SLURM_CLI_DELIMITER}" for field in JOB_DATA_SLURM_FIELDS
        ]
        output_spec = ",".join(formatted_fields)
        return self._parse_squeue(
            gen_squeue_lines=_gen_lines(
                self.__popen(["squeue", "--all", "-O", output_spec, "--noheader"])
            ),
            attributes=attributes,
            derived_cluster_fetcher=derived_cluster_fetcher,
            logger=logger,
        )

    def sinfo(self) -> Iterable[str]:
        return _gen_lines(self.__popen(["sinfo", "--all", "-N", "-o", "%all"]))

    def sdiag_structured(self) -> Sdiag:
        slurm_version = clusterscope.slurm_version()

        if slurm_version >= (23, 2):
            sdiag_output = json.loads(
                subprocess.check_output(["sdiag", "--all", "--json"], text=True)
            )

            return Sdiag(
                server_thread_count=sdiag_output["statistics"]["server_thread_count"],
                agent_queue_size=sdiag_output["statistics"]["agent_queue_size"],
                agent_count=sdiag_output["statistics"]["agent_count"],
                agent_thread_count=sdiag_output["statistics"]["agent_thread_count"],
                dbd_agent_queue_size=sdiag_output["statistics"]["dbd_agent_queue_size"],
            )

        sdiag_output = subprocess.check_output(["sdiag", "--all"], text=True)
        metric_names = {
            "Server thread count:": "server_thread_count",
            "Agent queue size:": "agent_queue_size",
            "Agent count:": "agent_count",
            "Agent thread count:": "agent_thread_count",
            "DBD Agent queue size:": "dbd_agent_queue_size",
        }
        data = {
            "server_thread_count": 0,
            "agent_queue_size": 0,
            "agent_count": 0,
            "agent_thread_count": 0,
            "dbd_agent_queue_size": 0,
        }

        for sdiag_name, name in metric_names.items():
            lines = re.search(rf".*{sdiag_name}.*", sdiag_output)
            assert lines is not None, f"Sdiag metric {sdiag_name} not found: {lines}"
            data[name] = int(lines.group().strip(f"{sdiag_name}"))
        return Sdiag(**data)

    def sinfo_structured(self) -> Sinfo:
        fieldnames = [f.name for f in fields(SinfoRow)]

        # if this isn't large enough, sinfo will truncate the output
        field_width = 256
        output_separator = "|"
        output_spec = f"{output_separator},".join(
            f"{f}:{field_width}" for f in fieldnames
        )
        restkey = None
        csvr = csv.DictReader(
            _gen_lines(
                self.__popen(["sinfo", "--all", "-N", "-O", output_spec, "--noheader"])
            ),
            delimiter=output_separator,
            fieldnames=fieldnames,
            restkey=restkey,
        )

        nodes = []
        for r in csvr:
            try:
                extra_fields = r[restkey]
            except KeyError:
                pass
            else:
                if not isinstance(extra_fields, list):
                    raise TypeError(
                        f"Expected extra fields to be 'list', but got '{type(extra_fields).__name__}'"
                    )

                if len(extra_fields) != 0:
                    logger.warning(f"Extra fields are non-empty: {extra_fields}")

                del r[restkey]
            row = SinfoRow(**r)
            alloc_cpus, _, _, _ = row.cpusstate.strip().split("/", maxsplit=3)
            sinfo_node = SinfoNode(
                alloc_cpus=int(alloc_cpus),
                total_cpus=int(row.cpus.strip()),
                gres=row.gres.strip(),
                gres_used=row.gresused.strip(),
                name=row.nodelist.strip(),
                state=row.statelong.strip(),
                partition=row.partitionname.strip(),
            )
            nodes.append(sinfo_node)
        return Sinfo(nodes=nodes)

    def sacctmgr_qos(self) -> Iterable[str]:
        return _gen_lines(self.__popen(["sacctmgr", "show", "qos", "-P"]))

    def sacctmgr_user(self) -> Iterable[str]:
        return _gen_lines(
            self.__popen(["sacctmgr", "show", "user", "format=User", "-nP"])
        )

    def sacctmgr_user_info(self, username: str) -> Iterable[str]:
        return _gen_lines(
            self.__popen(
                [
                    "sacctmgr",
                    "show",
                    "user",
                    username,
                    "withassoc",
                    "format=User,DefaultAccount,Account,DefaultQOS,QOS",
                    "-P",
                ]
            )
        )

    def sacct_running(self) -> Generator[str, None, None]:
        return get_sacct_lines(
            self.__popen(
                [
                    "sacct",
                    "-P",
                    "-s",
                    "running,r",
                    "--delimiter",
                    SLURM_CLI_DELIMITER,
                    "-a",
                    "-o",
                    "all",
                    "--duplicates",
                    "--noconvert",
                ],
            ),
            SLURM_CLI_DELIMITER,
        )

    def scontrol_partition(self) -> Iterable[str]:
        return _gen_lines(self.__popen(["scontrol", "show", "partition", "-a", "-o"]))

    def scontrol_config(self) -> Iterable[str]:
        return _gen_lines(self.__popen(["scontrol", "show", "config"]))

    def count_runaway_jobs(self) -> int:
        p = subprocess.Popen(
            "yes N | sudo sacctmgr show runaway -P | grep 'RUNNING' | wc -l",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        lines = p.stdout
        assert lines is not None, "It should be piped due to subprocess.PIPE"
        for st in lines:
            return int(st)
        raise Exception(f"Could not count sacctmgr show runaway lines: {lines}")
