# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import csv
import json
import logging
import re
import subprocess
from dataclasses import fields
from datetime import datetime, timezone
from typing import (
    Any,
    Callable,
    cast,
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
from gcm.schemas.slurm.sinfo_node import NodeData, SinfoNode
from gcm.schemas.slurm.sinfo_row import SinfoRow
from gcm.schemas.slurm.sprio import SPRIO_FORMAT_SPEC, SPRIO_HEADER
from gcm.schemas.slurm.squeue import JOB_DATA_SLURM_FIELDS, JobData
from gcm.schemas.slurm.sshare import SshareRow

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

logger = logging.getLogger(__name__)


def _json_number(value: Any) -> int | None:
    """Unwrap a Slurm JSON number, including NoVal objects."""
    if value is None:
        return None
    if isinstance(value, dict):
        if not value.get("set", True) or value.get("infinite", False):
            return None
        value = value.get("number")
    if value is None:
        return None
    return int(value)


def _json_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _state_suffix(states: set[str]) -> str:
    for flag, suffix in (
        ("MAINTENANCE", "$"),
        ("REBOOT_ISSUED", "^"),
        ("REBOOT_REQUESTED", "@"),
        ("POWERING_UP", "#"),
        ("POWERING_DOWN", "%"),
        ("POWERED_DOWN", "~"),
        ("POWER_DOWN", "!"),
        ("NOT_RESPONDING", "*"),
    ):
        if flag in states:
            return suffix
    return ""


def _base_node_state(state_list: list[str]) -> str:
    base_states = {
        "ALLOCATED",
        "DOWN",
        "ERROR",
        "FUTURE",
        "IDLE",
        "MIXED",
        "UNKNOWN",
    }
    for state in state_list:
        if state.upper() in base_states:
            return state.lower()
    return state_list[0].lower() if state_list else "unknown"


def _drain_or_fail_state(states: set[str], base: str, suffix: str) -> str | None:
    if "DRAIN" in states:
        draining = "COMPLETING" in states or base in {"allocated", "mixed"}
        return ("draining" if draining else "drained") + suffix
    if "FAIL" in states:
        failing = "COMPLETING" in states or base == "allocated"
        return ("failing" if failing else "fail") + suffix
    return None


def _format_node_state(value: Any) -> str:
    """Render Slurm JSON state tokens like sinfo's long STATE column."""
    state_list = _json_strings(value)
    states = {state.upper() for state in state_list}
    base = _base_node_state(state_list)
    suffix = _state_suffix(states)

    if "INVALID_REG" in states:
        return "inval"
    drain_or_fail_state = _drain_or_fail_state(states, base, suffix)
    if drain_or_fail_state is not None:
        return drain_or_fail_state
    if "MAINTENANCE" in states and base not in {"allocated", "down", "mixed"}:
        return "maint" + ("*" if "NOT_RESPONDING" in states else "")
    if "REBOOT_ISSUED" in states and base not in {"allocated", "mixed"}:
        return "reboot^"
    if "REBOOT_REQUESTED" in states and base not in {"allocated", "mixed"}:
        return "reboot" + ("*" if "NOT_RESPONDING" in states else "")
    if base == "idle" and "RESERVED" in states:
        return "reserved"
    if base == "idle" and "PLANNED" in states:
        return "planned"
    if base == "allocated" and "COMPLETING" in states and not suffix:
        return "allocated+"
    return base + suffix


def _format_reason_timestamp(value: Any) -> str:
    timestamp = _json_number(value)
    if timestamp is None or timestamp == 0:
        return "Unknown"
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _node_partitions(node: Mapping[str, Any]) -> list[str]:
    partitions = _json_strings(node.get("partitions"))
    if len(partitions) == 1 and "," in partitions[0]:
        partitions = partitions[0].split(",")
    return partitions or [""]


def _node_data_from_nodes(
    nodes: Iterable[Mapping[str, Any]],
    num_rows: int,
    derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
    logger: logging.Logger,
    attributes: Optional[dict[Hashable, Any]] = None,
) -> Generator[NodeData, None, None]:
    for node in nodes:
        for partition in _node_partitions(node):
            allocated = _json_number(node.get("alloc_cpus")) or 0
            idle = _json_number(node.get("alloc_idle_cpus", node.get("idle_cpus"))) or 0
            total = _json_number(node.get("cpus")) or 0
            free_mem = _json_number(node.get("free_mem"))
            real_memory = _json_number(node.get("real_memory"))
            message: dict[Hashable, Any] = {
                "num_rows": num_rows,
                **(attributes or {}),
                "NODELIST": str(node["name"]),
                "PARTITION": partition,
                "CPUS(A/I/O/T)": f"{allocated}/{idle}/{max(total - allocated - idle, 0)}/{total}",
                "FREE_MEM": "" if free_mem is None else str(free_mem),
                "MEMORY": "" if real_memory is None else str(real_memory),
                "GRES": str(node.get("gres") or "N/A"),
                "USER": str(node.get("owner") or "Unknown"),
                "REASON": str(node.get("reason") or "none"),
                "TIMESTAMP": _format_reason_timestamp(node.get("reason_changed_at")),
                "ACTIVE_FEATURES": ",".join(_json_strings(node.get("active_features"))),
                "STATE": _format_node_state(node.get("state")),
                "RESERVATION": str(node.get("reservation") or ""),
            }
            message["derived_cluster"] = derived_cluster_fetcher(message)
            yield instantiate_dataclass(NodeData, message, logger=logger)


def _nodes_from_sinfo_rows(
    rows: Iterable[Mapping[str, Any]],
) -> Generator[dict[str, Any], None, None]:
    for row in rows:
        for name in row["nodes"]["nodes"]:
            yield {
                "name": name,
                "partitions": [row["partition"]["name"]],
                "alloc_cpus": row["cpus"]["allocated"],
                "alloc_idle_cpus": row["cpus"]["idle"],
                "cpus": row["cpus"]["total"],
                "free_mem": row["memory"]["free"]["minimum"],
                "real_memory": row["memory"]["minimum"],
                "gres": row["gres"]["total"],
                "owner": row["reason"]["user"],
                "reason": row["reason"]["description"],
                "reason_changed_at": row["reason"]["time"],
                "active_features": row["features"]["active"],
                "state": row["node"]["state"],
                "reservation": row["reservation"],
            }


def node_data_from_sinfo_json(
    data: Mapping[str, Any],
    derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
    logger: logging.Logger,
    attributes: Optional[dict[Hashable, Any]] = None,
) -> Generator[NodeData, None, None]:
    """Yield nodes from the versioned sinfo JSON schema."""
    rows = data.get("sinfo", [])
    num_rows = sum(len(row["nodes"]["nodes"]) for row in rows)
    yield from _node_data_from_nodes(
        _nodes_from_sinfo_rows(rows),
        num_rows,
        attributes=attributes,
        derived_cluster_fetcher=derived_cluster_fetcher,
        logger=logger,
    )


def node_data_from_slurmrestd_json(
    data: Mapping[str, Any],
    derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
    logger: logging.Logger,
    attributes: Optional[dict[Hashable, Any]] = None,
) -> Generator[NodeData, None, None]:
    """Yield nodes from the slurmrestd /nodes response schema."""
    nodes = data.get("nodes", [])
    num_rows = sum(len(_node_partitions(node)) for node in nodes)
    yield from _node_data_from_nodes(
        nodes,
        num_rows,
        attributes=attributes,
        derived_cluster_fetcher=derived_cluster_fetcher,
        logger=logger,
    )


def add_pending_resources(message: dict[Any, Any]) -> None:
    """Adds an additional field ("PENDING_RESOURCES") to squeue output that tracks if the job is ready to be scheduled and waiting for resources."""
    if (
        message.get("STATE") == "PENDING"
        and message.get("REASON") in PENDING_RESOURCE_REASONS
    ):
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

    def sinfo(
        self,
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Generator[NodeData, None, None]:
        """Get node information in the stable NodeData schema."""

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

    def scontrol_topology(self) -> Iterable[str]:
        """Get lines of scontrol topology information."""

    def count_runaway_jobs(self) -> int:
        """Return the count of runaway jobs"""

    def sprio(self) -> Iterable[str]:
        """Get lines of sprio output showing job priority factors.
        Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.
        If an error occurs during execution, RuntimeError should be raised.
        """

    def sshare(self) -> Iterable[str]:
        """Get lines of sshare output showing fair-share data.
        Each line should be pipe separated.
        The first line defines the fieldnames. The rest are the rows.
        Lines should not have a trailing newline.
        If an error occurs during execution, RuntimeError should be raised.
        """

    def sshare_structured(self) -> Iterable[SshareRow]:
        """Get fair-share data as structured SshareRow instances."""


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

    def sinfo(
        self,
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Generator[NodeData, None, None]:
        output = "\n".join(_gen_lines(self.__popen(["sinfo", "--all", "-N", "--json"])))
        return node_data_from_sinfo_json(
            json.loads(output),
            attributes=attributes,
            derived_cluster_fetcher=derived_cluster_fetcher,
            logger=logger,
        )

    def sdiag_structured(self) -> Sdiag:
        slurm_version = clusterscope.slurm_version()

        if slurm_version >= (23, 2):
            sdiag_output = json.loads(
                subprocess.check_output(["sdiag", "--all", "--json"], text=True)
            )
            stats = sdiag_output["statistics"]

            # Extract nested objects (use `or {}` to handle both missing keys
            # and explicit None values from sdiag).
            schedule_exit = stats.get("schedule_exit") or {}
            bf_exit = stats.get("bf_exit") or {}

            # Extract timestamp fields (they have {set, infinite, number} structure).
            # Use `or {}` to handle both missing keys AND explicit `null` values
            # from sdiag JSON; `.get(key, {})` alone returns None when the key
            # is present but null, and `.get("set")` then raises AttributeError.
            req_time_obj = stats.get("req_time") or {}
            req_time_start_obj = stats.get("req_time_start") or {}
            job_states_ts_obj = stats.get("job_states_ts") or {}
            bf_when_last_cycle_obj = stats.get("bf_when_last_cycle") or {}

            # Serialize RPCs to JSON strings
            rpcs_by_message_type = stats.get("rpcs_by_message_type", [])
            rpcs_by_user = stats.get("rpcs_by_user", [])

            result = Sdiag(
                # Required fields
                server_thread_count=stats.get("server_thread_count"),
                agent_queue_size=stats.get("agent_queue_size"),
                agent_count=stats.get("agent_count"),
                agent_thread_count=stats.get("agent_thread_count"),
                dbd_agent_queue_size=stats.get("dbd_agent_queue_size"),
                # Schedule cycle
                schedule_cycle_max=stats.get("schedule_cycle_max"),
                schedule_cycle_mean=stats.get("schedule_cycle_mean"),
                schedule_cycle_sum=stats.get("schedule_cycle_sum"),
                schedule_cycle_total=stats.get("schedule_cycle_total"),
                schedule_cycle_per_minute=stats.get("schedule_cycle_per_minute"),
                schedule_queue_length=stats.get("schedule_queue_length"),
                schedule_cycle_last=stats.get("schedule_cycle_last"),
                schedule_cycle_mean_depth=stats.get("schedule_cycle_mean_depth"),
                schedule_cycle_depth=stats.get("schedule_cycle_depth"),
                # Schedule exit
                schedule_exit_end_job_queue=schedule_exit.get("end_job_queue"),
                schedule_exit_default_queue_depth=schedule_exit.get(
                    "default_queue_depth"
                ),
                schedule_exit_max_job_start=schedule_exit.get("max_job_start"),
                schedule_exit_max_rpc_cnt=schedule_exit.get("max_rpc_cnt"),
                schedule_exit_max_sched_time=schedule_exit.get("max_sched_time"),
                schedule_exit_licenses=schedule_exit.get("licenses"),
                # Job stats
                sdiag_jobs_submitted=stats.get("jobs_submitted"),
                sdiag_jobs_started=stats.get("jobs_started"),
                sdiag_jobs_completed=stats.get("jobs_completed"),
                sdiag_jobs_canceled=stats.get("jobs_canceled"),
                sdiag_jobs_failed=stats.get("jobs_failed"),
                sdiag_jobs_pending=stats.get("jobs_pending"),
                sdiag_jobs_running=stats.get("jobs_running"),
                # Backfill stats
                bf_backfilled_jobs=stats.get("bf_backfilled_jobs"),
                bf_last_backfilled_jobs=stats.get("bf_last_backfilled_jobs"),
                bf_backfilled_het_jobs=stats.get("bf_backfilled_het_jobs"),
                bf_cycle_counter=stats.get("bf_cycle_counter"),
                bf_cycle_mean=stats.get("bf_cycle_mean"),
                bf_cycle_sum=stats.get("bf_cycle_sum"),
                bf_cycle_max=stats.get("bf_cycle_max"),
                bf_cycle_last=stats.get("bf_cycle_last"),
                bf_depth_mean=stats.get("bf_depth_mean"),
                bf_depth_mean_try=stats.get("bf_depth_mean_try"),
                bf_depth_sum=stats.get("bf_depth_sum"),
                bf_depth_try_sum=stats.get("bf_depth_try_sum"),
                bf_last_depth=stats.get("bf_last_depth"),
                bf_last_depth_try=stats.get("bf_last_depth_try"),
                bf_queue_len=stats.get("bf_queue_len"),
                bf_queue_len_mean=stats.get("bf_queue_len_mean"),
                bf_queue_len_sum=stats.get("bf_queue_len_sum"),
                bf_table_size=stats.get("bf_table_size"),
                bf_table_size_sum=stats.get("bf_table_size_sum"),
                bf_table_size_mean=stats.get("bf_table_size_mean"),
                bf_when_last_cycle=(
                    bf_when_last_cycle_obj.get("number")
                    if bf_when_last_cycle_obj.get("set")
                    else None
                ),
                bf_active=(
                    bool(stats.get("bf_active"))
                    if stats.get("bf_active") is not None
                    else None
                ),
                # Backfill exit
                bf_exit_end_job_queue=bf_exit.get("end_job_queue"),
                bf_exit_max_job_start=bf_exit.get("bf_max_job_start"),
                bf_exit_max_job_test=bf_exit.get("bf_max_job_test"),
                bf_exit_max_time=bf_exit.get("bf_max_time"),
                bf_exit_node_space_size=bf_exit.get("bf_node_space_size"),
                bf_exit_state_changed=bf_exit.get("state_changed"),
                # Timing
                req_time=(
                    req_time_obj.get("number") if req_time_obj.get("set") else None
                ),
                req_time_start=(
                    req_time_start_obj.get("number")
                    if req_time_start_obj.get("set")
                    else None
                ),
                gettimeofday_latency=stats.get("gettimeofday_latency"),
                job_states_ts=(
                    job_states_ts_obj.get("number")
                    if job_states_ts_obj.get("set")
                    else None
                ),
                parts_packed=stats.get("parts_packed"),
                # JSON blobs
                rpcs_by_message_type_json=(
                    json.dumps(rpcs_by_message_type)
                    if rpcs_by_message_type is not None
                    else "[]"
                ),
                rpcs_by_user_json=(
                    json.dumps(rpcs_by_user) if rpcs_by_user is not None else "[]"
                ),
            )

            # Reset sdiag counters after collection
            self._reset_sdiag_counters()

            return result

        sdiag_output = subprocess.check_output(["sdiag", "--all"], text=True)
        metric_names = {
            "Server thread count:": "server_thread_count",
            "Agent queue size:": "agent_queue_size",
            "Agent count:": "agent_count",
            "Agent thread count:": "agent_thread_count",
            "DBD Agent queue size:": "dbd_agent_queue_size",
        }
        # Legacy (slurm < 23.2) text-parse path only emits int/None values;
        # the new JSON-blob and string-typed Sdiag fields are only populated
        # via the slurm >= 23.2 JSON branch above. Keep the type narrow.
        data: dict[str, Optional[int]] = {
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

        optional_metric_names = {
            "Schedule cycle max:": "schedule_cycle_max",
            "Schedule cycle mean:": "schedule_cycle_mean",
            "Schedule cycle sum:": "schedule_cycle_sum",
            "Schedule cycle total:": "schedule_cycle_total",
            "Schedule cycle per minute:": "schedule_cycle_per_minute",
            "Schedule queue length:": "schedule_queue_length",
            "Jobs submitted:": "sdiag_jobs_submitted",
            "Jobs started:": "sdiag_jobs_started",
            "Jobs completed:": "sdiag_jobs_completed",
            "Jobs canceled:": "sdiag_jobs_canceled",
            "Jobs failed:": "sdiag_jobs_failed",
            "Jobs pending:": "sdiag_jobs_pending",
            "Jobs running:": "sdiag_jobs_running",
            "Total backfilled jobs \\(since last slurm start\\):": "bf_backfilled_jobs",
            "Backfill cycle mean:": "bf_cycle_mean",
            "Backfill cycle sum:": "bf_cycle_sum",
            "Backfill cycle max:": "bf_cycle_max",
            "Backfill queue length:": "bf_queue_len",
        }

        for sdiag_name, name in optional_metric_names.items():
            match = re.search(rf"{sdiag_name}\s*(\d+)", sdiag_output)
            if match:
                data[name] = int(match.group(1))
            else:
                data[name] = None

        # Cast to Any for the splat: mypy cannot reconcile dict[str, int|None]
        # values against Sdiag's mixed int|bool|str|None fields without per-key
        # checks. At runtime this path only emits int/None values; non-int
        # Sdiag fields (bf_active, rpcs_by_*_json) fall back to their None
        # defaults.
        result = Sdiag(**cast(dict[str, Any], data))

        # Reset sdiag counters after collection
        self._reset_sdiag_counters()

        return result

    def _reset_sdiag_counters(self) -> None:
        """Reset sdiag counters after collection.

        This requires appropriate permissions (typically root or SlurmUser).
        If the reset fails due to permission issues, a warning is logged.
        """
        try:
            subprocess.run(
                ["sdiag", "--reset"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to reset sdiag counters: {e.stderr.strip()}")

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

    def scontrol_topology(self) -> Iterable[str]:
        return _gen_lines(self.__popen(["scontrol", "show", "topo"]))

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

    def sprio(self) -> Iterable[str]:
        # Sort by partition (r) and priority descending (-y) for consistent ordering
        yield SPRIO_HEADER
        yield from _gen_lines(
            self.__popen(["sprio", "-h", "--sort=r,-y", "-o", SPRIO_FORMAT_SPEC])
        )

    def sshare(self) -> Iterable[str]:
        return _gen_lines(self.__popen(["sshare", "-a", "-P"]))

    def sshare_structured(self) -> Iterable[SshareRow]:
        raise NotImplementedError(
            "sshare_structured is not yet implemented for SlurmCliClient; "
            "use SlurmRestClient"
        )
