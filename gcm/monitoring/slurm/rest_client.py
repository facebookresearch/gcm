# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import logging
from typing import (
    Any,
    Callable,
    Generator,
    Hashable,
    Iterable,
    Mapping,
    NoReturn,
    Optional,
)

import requests
from gcm.monitoring.dataclass_utils import instantiate_dataclass
from gcm.monitoring.slurm.client import add_pending_resources, SlurmClient
from gcm.monitoring.slurm.constants import SLURM_CLI_DELIMITER
from gcm.schemas.slurm.sdiag import Sdiag
from gcm.schemas.slurm.sinfo import Sinfo
from gcm.schemas.slurm.sinfo_node import SinfoNode
from gcm.schemas.slurm.squeue import JobData, REST_TO_SQUEUE_FIELD_MAP
from gcm.schemas.slurm.sshare import SshareRow

logger = logging.getLogger(__name__)


class SlurmRestClient(SlurmClient):
    """Slurm client that queries slurmrestd HTTP endpoints.

    Provides the same SlurmClient Protocol interface as SlurmCliClient
    but queries the Slurm REST API instead of executing subprocess commands.
    Useful for environments where Slurm CLI tools are not available on
    monitoring hosts.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: Optional[str] = None,
        api_version: str = "v0.0.40",
        session: Optional[requests.Session] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = session or requests.Session()
        if token is not None:
            self.session.headers["X-SLURM-USER-TOKEN"] = token

    def _get(
        self, endpoint: str, params: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        """Issue a GET request to the Slurm REST API and return JSON."""
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Slurm REST API request failed: {response.status_code} {url}"
            )
        data: dict[str, Any] = response.json()
        return data

    def _map_job_fields(self, job: dict[str, Any]) -> dict[Hashable, Any]:
        """Map REST API job fields to CLI squeue field names."""
        row: dict[Hashable, Any] = {}
        for rest_key, squeue_key in REST_TO_SQUEUE_FIELD_MAP.items():
            value = job.get(rest_key, "")
            # Handle nested dicts (e.g. time_limit may be {"number": N, ...})
            if isinstance(value, dict):
                value = value.get("number", value.get("set", str(value)))
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            row[squeue_key] = str(value) if value is not None else ""
        return row

    def squeue(
        self,
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Iterable[JobData]:
        data = self._get(f"/slurm/{self.api_version}/jobs")
        jobs = data.get("jobs", [])
        for job in jobs:
            row = self._map_job_fields(job)
            row.update(attributes or {})
            add_pending_resources(row)
            row["derived_cluster"] = derived_cluster_fetcher(row)
            yield instantiate_dataclass(JobData, row, logger=logger)

    def sinfo(self) -> Iterable[str]:
        data = self._get(f"/slurm/{self.api_version}/nodes")
        nodes = data.get("nodes", [])
        if not nodes:
            return []
        field_names = list(dict.fromkeys(k for node in nodes for k in node.keys()))
        yield "|".join(field_names)
        for node in nodes:
            yield "|".join(str(node.get(f, "")) for f in field_names)

    def sdiag_structured(self) -> Sdiag:
        data = self._get(f"/slurm/{self.api_version}/diag")
        stats = data.get("statistics", {})
        result = Sdiag(
            server_thread_count=stats.get("server_thread_count"),
            agent_queue_size=stats.get("agent_queue_size"),
            agent_count=stats.get("agent_count"),
            agent_thread_count=stats.get("agent_thread_count"),
            dbd_agent_queue_size=stats.get("dbd_agent_queue_size"),
            schedule_cycle_max=stats.get("schedule_cycle_max"),
            schedule_cycle_mean=stats.get("schedule_cycle_mean"),
            schedule_cycle_sum=stats.get("schedule_cycle_sum"),
            schedule_cycle_total=stats.get("schedule_cycle_total"),
            schedule_cycle_per_minute=stats.get("schedule_cycle_per_minute"),
            schedule_queue_length=stats.get("schedule_queue_length"),
            sdiag_jobs_submitted=stats.get("jobs_submitted"),
            sdiag_jobs_started=stats.get("jobs_started"),
            sdiag_jobs_completed=stats.get("jobs_completed"),
            sdiag_jobs_canceled=stats.get("jobs_canceled"),
            sdiag_jobs_failed=stats.get("jobs_failed"),
            sdiag_jobs_pending=stats.get("jobs_pending"),
            sdiag_jobs_running=stats.get("jobs_running"),
            bf_backfilled_jobs=stats.get("bf_backfilled_jobs"),
            bf_cycle_mean=stats.get("bf_cycle_mean"),
            bf_cycle_sum=stats.get("bf_cycle_sum"),
            bf_cycle_max=stats.get("bf_cycle_max"),
            bf_queue_len=stats.get("bf_queue_len"),
        )
        return result

    def sinfo_structured(self) -> Sinfo:
        data = self._get(f"/slurm/{self.api_version}/nodes")
        nodes_data = data.get("nodes", [])
        nodes = []
        for n in nodes_data:
            alloc_cpus = n.get("alloc_cpus", 0)
            total_cpus = n.get("cpus", 0)
            gres = n.get("gres", "")
            gres_used = n.get("gres_used", "")
            name = n.get("name", n.get("hostname", ""))
            state = n.get("state", "")
            # Partitions may be a list; take the first one
            partitions = n.get("partitions", [])
            partition = partitions[0] if partitions else ""
            nodes.append(
                SinfoNode(
                    alloc_cpus=int(alloc_cpus),
                    total_cpus=int(total_cpus),
                    gres=str(gres),
                    gres_used=str(gres_used),
                    name=str(name),
                    state=str(state),
                    partition=str(partition),
                )
            )
        return Sinfo(nodes=nodes)

    def sacctmgr_qos(self) -> Iterable[str]:
        data = self._get(f"/slurmdb/{self.api_version}/qos")
        qos_list = data.get("qos", [])
        if not qos_list:
            return []
        field_names = list(dict.fromkeys(k for qos in qos_list for k in qos.keys()))
        yield "|".join(field_names)
        for qos in qos_list:
            yield "|".join(str(qos.get(f, "")) for f in field_names)

    def sacctmgr_user(self) -> Iterable[str]:
        data = self._get(f"/slurmdb/{self.api_version}/users")
        users = data.get("users", [])
        for user in users:
            yield str(user.get("name", ""))

    def sacctmgr_user_info(self, username: str) -> Iterable[str]:
        data = self._get(f"/slurmdb/{self.api_version}/users/{username}")
        users = data.get("users", [])
        if not users:
            return []
        header = "User|DefaultAccount|Account|DefaultQOS|QOS"
        yield header
        for user in users:
            default_account = str(user.get("default", {}).get("account", ""))
            default_qos = str(user.get("default", {}).get("qos", ""))
            associations = user.get("associations", [])
            if associations:
                for assoc in associations:
                    account = str(assoc.get("account", ""))
                    qos_list = assoc.get("qos", [])
                    qos_str = ",".join(str(q) for q in qos_list)
                    yield "|".join(
                        [username, default_account, account, default_qos, qos_str]
                    )
            else:
                yield "|".join([username, default_account, "", default_qos, ""])

    def sacct_running(self) -> Generator[str, None, None]:
        data = self._get(
            f"/slurmdb/{self.api_version}/jobs",
            params={"state": "running"},
        )
        jobs = data.get("jobs", [])
        if not jobs:
            return
        field_names = list(dict.fromkeys(k for job in jobs for k in job.keys()))
        yield SLURM_CLI_DELIMITER.join(field_names)
        for job in jobs:
            yield SLURM_CLI_DELIMITER.join(str(job.get(f, "")) for f in field_names)

    def scontrol_partition(self) -> Iterable[str]:
        data = self._get(f"/slurm/{self.api_version}/partitions")
        partitions = data.get("partitions", [])
        for part in partitions:
            # Format as key=value pairs on a single line, matching scontrol -o
            pairs = [f"{k}={v}" for k, v in part.items()]
            yield " ".join(pairs)

    def scontrol_config(self) -> NoReturn:
        raise NotImplementedError(
            "scontrol_config is not available via Slurm REST API; "
            "the /slurmdb/config endpoint returns slurmdbd config, "
            "not slurmctld config. Use SlurmCliClient"
        )

    def count_runaway_jobs(self) -> NoReturn:
        raise NotImplementedError(
            "count_runaway_jobs is not available via Slurm REST API; "
            "use SlurmCliClient"
        )

    def sprio(self) -> NoReturn:
        raise NotImplementedError(
            "sprio is not available via Slurm REST API; use SlurmCliClient"
        )

    def sshare(self) -> Iterable[str]:
        data = self._get(f"/slurm/{self.api_version}/shares")
        shares = data.get("shares", {}).get("shares", [])
        if not shares:
            return []
        yield "Account|User|RawShares|NormShares|RawUsage|NormUsage|FairShare"
        for share in shares:
            yield "|".join(
                [
                    str(share.get("name", "")),
                    str(share.get("user", "")),
                    str(share.get("shares", {}).get("raw", "")),
                    str(share.get("shares", {}).get("normalized", "")),
                    str(share.get("usage", {}).get("raw", "")),
                    str(share.get("usage", {}).get("normalized", "")),
                    str(share.get("fairshare", {}).get("factor", "")),
                ]
            )

    def sshare_structured(self) -> Iterable[SshareRow]:
        data = self._get(f"/slurm/{self.api_version}/shares")
        shares = data.get("shares", {}).get("shares", [])
        for share in shares:
            yield SshareRow(
                Account=str(share.get("name", "")),
                User=str(share.get("user", "")),
                RawShares=str(share.get("shares", {}).get("raw", "")),
                NormShares=str(share.get("shares", {}).get("normalized", "")),
                RawUsage=str(share.get("usage", {}).get("raw", "")),
                NormUsage=str(share.get("usage", {}).get("normalized", "")),
                FairShare=str(share.get("fairshare", {}).get("factor", "")),
            )
