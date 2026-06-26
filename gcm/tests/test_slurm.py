# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
import subprocess
from functools import partial
from importlib import resources
from unittest.mock import create_autospec, MagicMock, patch

import pytest
from gcm.monitoring.clock import time_to_time_aware
from gcm.monitoring.slurm.client import SlurmCliClient

from gcm.monitoring.slurm.derived_cluster import get_derived_cluster

from gcm.schemas.slurm.sinfo import Sinfo
from gcm.schemas.slurm.sinfo_node import SinfoNode
from gcm.schemas.slurm.squeue import _truncated_nodelist, JobData
from gcm.tests import data

TEST_CLUSTER = "test_cluster"


class TestSlurmCliClient:
    @staticmethod
    @pytest.mark.parametrize(
        "expected",
        [
            [
                JobData(
                    collection_unixtime=123,
                    cluster=TEST_CLUSTER,
                    derived_cluster=TEST_CLUSTER,
                    PENDING_RESOURCES="False",
                    GPUS_REQUESTED=0,
                    MIN_CPUS=1,
                    JOBID="45704744",
                    JOBID_RAW="45704744",
                    NAME="bash",
                    TIME_LIMIT="14-00:00:00",
                    MIN_MEMORY=0,
                    COMMAND="bash",
                    PRIORITY=0.00017607258637,
                    STATE="RUNNING",
                    USER="test_user",
                    CPUS=24,
                    NODES=1,
                    TIME_LEFT="13-06:37:11",
                    TIME_USED="17:22:49",
                    NODELIST=["node1321"],
                    DEPENDENCY="(null)",
                    EXC_NODES=None,
                    START_TIME=time_to_time_aware("2025-04-10T13:44:41"),
                    SUBMIT_TIME=time_to_time_aware("2025-04-10T13:44:39"),
                    ELIGIBLE_TIME=time_to_time_aware("2025-04-10T13:44:39"),
                    ACCRUE_TIME=time_to_time_aware("2025-04-10T13:44:40"),
                    PENDING_TIME=100,
                    COMMENT="(null)",
                    PARTITION="partition",
                    ACCOUNT="account",
                    QOS="normal",
                    REASON="None",
                    TRES_GPUS_ALLOCATED=2,
                    RESERVATION="",
                    REQUEUE="1",
                    FEATURE="gpu",
                    RESTARTCNT=1,
                    SCHEDNODES=["node1321"],
                    TRES_CPU_ALLOCATED=24,
                    TRES_MEM_ALLOCATED=0,
                    TRES_NODE_ALLOCATED=1,
                    TRES_BILLING_ALLOCATED=112,
                    LAST_SCHED_EVAL=time_to_time_aware("2025-04-10T13:45:10"),
                ),
                JobData(
                    collection_unixtime=123,
                    cluster=TEST_CLUSTER,
                    derived_cluster=TEST_CLUSTER,
                    PENDING_RESOURCES="False",
                    GPUS_REQUESTED=1,
                    MIN_CPUS=1,
                    JOBID="42953390_320",
                    JOBID_RAW="42953598",
                    NAME="run1",
                    TIME_LIMIT="3-00:00:00",
                    MIN_MEMORY=60_000_000_000,
                    COMMAND="/test/run.sh",
                    PRIORITY=0.00017546257008,
                    STATE="RUNNING",
                    USER="test_user",
                    CPUS=1,
                    NODES=1,
                    TIME_LEFT="2-17:56:34",
                    TIME_USED="6:03:26",
                    NODELIST=["node1303"],
                    DEPENDENCY="(null)",
                    EXC_NODES=None,
                    START_TIME=time_to_time_aware("2025-03-06T21:01:21"),
                    SUBMIT_TIME=time_to_time_aware("2025-03-06T20:59:59"),
                    ELIGIBLE_TIME=time_to_time_aware("2025-03-06T20:59:59"),
                    ACCRUE_TIME=time_to_time_aware("2025-03-06T21:01:00"),
                    PENDING_TIME=82,
                    COMMENT="(null)",
                    PARTITION="partition",
                    ACCOUNT="account",
                    QOS="normal",
                    REASON="None",
                    TRES_GPUS_ALLOCATED=1,
                    RESERVATION="",
                    REQUEUE="1",
                    FEATURE="gpu",
                    RESTARTCNT=1,
                    SCHEDNODES=["node1303"],
                    TRES_CPU_ALLOCATED=1,
                    TRES_MEM_ALLOCATED=0,
                    TRES_NODE_ALLOCATED=1,
                    TRES_BILLING_ALLOCATED=34,
                    LAST_SCHED_EVAL=time_to_time_aware("2025-03-06T21:01:30"),
                ),
                JobData(
                    collection_unixtime=123,
                    cluster=TEST_CLUSTER,
                    derived_cluster=TEST_CLUSTER,
                    PENDING_RESOURCES="False",
                    GPUS_REQUESTED=8,
                    MIN_CPUS=80,
                    JOBID="42956774_3",
                    JOBID_RAW="42956774",
                    NAME="run3",
                    TIME_LIMIT="3-00:00:00",
                    MIN_MEMORY=60_000_000_000,
                    COMMAND="/test/run.sh",
                    PRIORITY=0.00000595580787,
                    STATE="RUNNING",
                    USER="test_user",
                    CPUS=2560,
                    NODES=32,
                    TIME_LEFT="2-23:55:01",
                    TIME_USED="4:59",
                    NODELIST=[
                        "node1281",
                        "node1282",
                        "node1283",
                        "node1284",
                        "node1285",
                        "node1286",
                        "node1287",
                        "node1288",
                        "node1301",
                        "node1302",
                        "node1303",
                        "node1304",
                        "node1309",
                        "node1310",
                        "node1311",
                        "node1312",
                        "node1365",
                        "node1366",
                        "node1367",
                        "node1368",
                        "node1369",
                        "node1370",
                        "node1371",
                        "node1372",
                        "node1377",
                        "node1378",
                        "node1379",
                        "node1380",
                        "node1381",
                        "node1382",
                        "node1383",
                        "node1384",
                    ],
                    DEPENDENCY="(null)",
                    EXC_NODES=None,
                    START_TIME=time_to_time_aware("2025-03-07T04:16:04"),
                    SUBMIT_TIME=time_to_time_aware("2025-03-07T04:15:46"),
                    ELIGIBLE_TIME=time_to_time_aware("2025-03-07T04:15:46"),
                    ACCRUE_TIME=time_to_time_aware("2025-03-07T04:16:03"),
                    PENDING_TIME=18,
                    COMMENT="(null)",
                    PARTITION="partition",
                    ACCOUNT="account",
                    QOS="normal",
                    REASON="None",
                    TRES_GPUS_ALLOCATED=256,
                    RESERVATION="",
                    REQUEUE="1",
                    FEATURE="gpu",
                    RESTARTCNT=6,
                    SCHEDNODES=[
                        "node1381",
                        "node1382",
                        "node1383",
                    ],
                    TRES_CPU_ALLOCATED=2560,
                    TRES_MEM_ALLOCATED=0,
                    TRES_NODE_ALLOCATED=32,
                    TRES_BILLING_ALLOCATED=0,
                    LAST_SCHED_EVAL=time_to_time_aware("2025-03-07T04:16:33"),
                ),
                JobData(
                    collection_unixtime=123,
                    cluster=TEST_CLUSTER,
                    derived_cluster=TEST_CLUSTER,
                    PENDING_RESOURCES="False",
                    GPUS_REQUESTED=0,
                    MIN_CPUS=1,
                    JOBID="22783212",
                    JOBID_RAW="22783212",
                    NAME="run4",
                    TIME_LIMIT="1:00:00",
                    MIN_MEMORY=10_500_000_000,
                    COMMAND="/test/run.sh",
                    PRIORITY=0.00018553552222,
                    STATE="PENDING",
                    USER="test_user",
                    CPUS=1,
                    NODES=1,
                    TIME_LEFT="1:00:00",
                    TIME_USED="0:00",
                    NODELIST=None,
                    DEPENDENCY="afterok:22783211_*(failed)",
                    EXC_NODES=None,
                    START_TIME="N/A",
                    SUBMIT_TIME=time_to_time_aware("2024-01-31T04:06:57"),
                    ELIGIBLE_TIME="N/A",
                    ACCRUE_TIME="N/A",
                    PENDING_TIME=0,
                    COMMENT="(null)",
                    PARTITION="partition",
                    ACCOUNT="account",
                    QOS="normal",
                    REASON="DependencyNeverSatisfied",
                    TRES_GPUS_ALLOCATED=0,
                    RESERVATION="",
                    REQUEUE="1",
                    FEATURE="gpu",
                    RESTARTCNT=123,
                    SCHEDNODES=[
                        "node1381",
                        "node1382",
                        "node1383",
                    ],
                    TRES_CPU_ALLOCATED=1,
                    TRES_MEM_ALLOCATED=10000,
                    TRES_NODE_ALLOCATED=1,
                    TRES_BILLING_ALLOCATED=2,
                    LAST_SCHED_EVAL="N/A",
                ),
                JobData(
                    collection_unixtime=123,
                    cluster=TEST_CLUSTER,
                    derived_cluster=TEST_CLUSTER,
                    PENDING_RESOURCES="False",
                    GPUS_REQUESTED=8,
                    MIN_CPUS=16,
                    JOBID="42271120_[7-8%1]",
                    JOBID_RAW="42271120",
                    NAME="run5",
                    TIME_LIMIT="3-00:00:00",
                    MIN_MEMORY=1_000_000_000_000,
                    COMMAND="/test/run.sh",
                    PRIORITY=0.00012484216134,
                    STATE="PENDING",
                    USER="test_user",
                    CPUS=320,
                    NODES=20,
                    TIME_LEFT="3-00:00:00",
                    TIME_USED="0:00",
                    NODELIST=None,
                    DEPENDENCY="(null)",
                    EXC_NODES=None,
                    START_TIME="N/A",
                    SUBMIT_TIME=time_to_time_aware("2025-02-26T15:29:14"),
                    ELIGIBLE_TIME="N/A",
                    ACCRUE_TIME="N/A",
                    PENDING_TIME=0,
                    COMMENT="(null)",
                    PARTITION="partition",
                    ACCOUNT="account",
                    QOS="normal",
                    REASON="JobArrayTaskLimit",
                    TRES_GPUS_ALLOCATED=160,
                    RESERVATION="",
                    REQUEUE="1",
                    FEATURE="gpu",
                    RESTARTCNT=10,
                    SCHEDNODES=[
                        "node1381",
                        "node1382",
                        "node1383",
                    ],
                    TRES_CPU_ALLOCATED=320,
                    TRES_MEM_ALLOCATED=1280500,
                    TRES_NODE_ALLOCATED=20,
                    TRES_BILLING_ALLOCATED=3040,
                    LAST_SCHED_EVAL="N/A",
                ),
            ]
        ],
    )
    def test_squeue(expected: list[JobData]) -> None:
        fake_popen = create_autospec(subprocess.Popen)
        fake_proc = fake_popen.return_value
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.wait.return_value = 0

        with resources.path(data, "sample-squeue-output.txt") as p:
            with p.open() as f:
                fake_proc.stdout = f
                c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))
                derived_cluster_fetcher = partial(
                    get_derived_cluster,
                    cluster=TEST_CLUSTER,
                    heterogeneous_cluster_v1=False,
                )
                actual = [
                    s
                    for s in c.squeue(
                        derived_cluster_fetcher=derived_cluster_fetcher,
                        attributes={
                            "cluster": TEST_CLUSTER,
                            "collection_unixtime": 123,
                        },
                        logger=logging.getLogger(),
                    )
                ]
        assert actual == expected

    @staticmethod
    def test_squeue_throws_if_popen_throws() -> None:
        fake_popen = MagicMock()
        fake_popen.side_effect = RuntimeError
        c = SlurmCliClient(popen=fake_popen)
        derived_cluster_fetcher = partial(
            get_derived_cluster, cluster=TEST_CLUSTER, heterogeneous_cluster_v1=False
        )
        with pytest.raises(RuntimeError):
            c.squeue(
                derived_cluster_fetcher=derived_cluster_fetcher,
                logger=logging.getLogger(),
            )

        fake_popen.assert_called_once()

    @staticmethod
    def test_sinfo_throws_if_popen_throws() -> None:
        fake_popen = MagicMock()
        fake_popen.side_effect = RuntimeError
        c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))

        with pytest.raises(RuntimeError):
            c.sinfo()

        fake_popen.assert_called_once()

    @staticmethod
    @pytest.mark.parametrize(
        "dataset, expected",
        [
            (
                "sinfo-output-for-structured.txt",
                Sinfo(
                    nodes=[
                        SinfoNode(
                            name="node1074",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:0(IDX:N/A)",
                            total_cpus=256,
                            alloc_cpus=0,
                            state="idle",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node1221",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=256,
                            state="allocated",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node1492",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=64,
                            state="mixed",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node1814",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=80,
                            state="mixed",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node2002",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=80,
                            state="mixed",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node2351",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=96,
                            state="mixed",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node2578",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=96,
                            state="mixed",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node2626",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:0(IDX:N/A)",
                            total_cpus=256,
                            alloc_cpus=0,
                            state="idle",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node2654",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:0",
                            total_cpus=256,
                            alloc_cpus=0,
                            state="drained$",
                            partition="learn",
                        ),
                        SinfoNode(
                            name="node2757",
                            gres="gpu:ampere:8",
                            gres_used="gpu:ampere:8(IDX:0-7)",
                            total_cpus=256,
                            alloc_cpus=96,
                            state="mixed",
                            partition="learn",
                        ),
                    ]
                ),
            ),
        ],
    )
    def test_sinfo_structured(dataset: str, expected: Sinfo) -> None:
        fake_popen = create_autospec(subprocess.Popen)
        fake_proc = fake_popen.return_value
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.wait.return_value = 0

        with resources.open_text(data, dataset) as f:
            fake_proc.stdout = f
            c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))
            actual = c.sinfo_structured()

        assert actual == expected

    @staticmethod
    @patch.object(SlurmCliClient, "_reset_sdiag_counters")
    @patch("clusterscope.slurm_version")
    @patch("subprocess.check_output")
    def test_parse_sdiag_json(
        mock_check_output: MagicMock,
        mock_slurm_version: MagicMock,
        mock_reset: MagicMock,
    ) -> None:
        mock_slurm_version.return_value = (23, 2)

        with resources.open_text(data, "sample-sdiag-output.json") as f:
            mock_check_output.return_value = f.read()

        c = SlurmCliClient()
        result = c.sdiag_structured()

        # Verify core fields from sample-sdiag-output.json
        assert result.server_thread_count == 4
        assert result.agent_queue_size == 5
        assert result.agent_count == 3
        assert result.agent_thread_count == 8
        assert result.dbd_agent_queue_size == 2
        assert result.schedule_cycle_max == 2788800
        assert result.schedule_cycle_mean == 1737702
        assert result.schedule_queue_length == 407
        assert result.sdiag_jobs_submitted == 504
        assert result.sdiag_jobs_running == 3273
        assert result.bf_backfilled_jobs == 287
        assert result.bf_cycle_mean == 37143463
        assert result.bf_queue_len == 411
        # Schedule exit + backfill exit
        assert result.schedule_exit_end_job_queue == 54
        assert result.schedule_exit_max_sched_time == 281
        assert result.bf_exit_end_job_queue == 10
        assert result.bf_exit_state_changed == 0
        # New fields added in this diff
        assert result.schedule_cycle_last == 2258381
        assert result.bf_last_backfilled_jobs == 287
        assert result.bf_cycle_last == 46552416
        assert result.bf_active is True
        assert result.gettimeofday_latency == 26
        # Verify rpcs_by_*_json are parseable JSON with expected shape, not
        # just non-None (addresses ai_diff_reviewer assertion-strength comment).
        assert result.rpcs_by_message_type_json is not None
        rpcs_by_type = json.loads(result.rpcs_by_message_type_json)
        assert isinstance(rpcs_by_type, list) and len(rpcs_by_type) > 0
        assert "message_type" in rpcs_by_type[0]
        assert "count" in rpcs_by_type[0]
        assert result.rpcs_by_user_json is not None
        rpcs_by_user = json.loads(result.rpcs_by_user_json)
        assert isinstance(rpcs_by_user, list) and len(rpcs_by_user) > 0
        assert "user" in rpcs_by_user[0]
        assert "count" in rpcs_by_user[0]
        mock_check_output.assert_called_once_with(
            ["sdiag", "--all", "--json"], text=True
        )
        mock_reset.assert_called_once()

    @staticmethod
    @patch.object(SlurmCliClient, "_reset_sdiag_counters")
    @patch("clusterscope.slurm_version")
    @patch("subprocess.check_output")
    def test_parse_sdiag_json_with_missing_fields(
        mock_check_output: MagicMock,
        mock_slurm_version: MagicMock,
        mock_reset: MagicMock,
    ) -> None:
        mock_slurm_version.return_value = (23, 2)

        minimal_json = json.dumps(
            {
                "statistics": {
                    "server_thread_count": 10,
                    "agent_queue_size": 5,
                    "agent_count": 3,
                    "agent_thread_count": 8,
                    "dbd_agent_queue_size": 2,
                }
            }
        )
        mock_check_output.return_value = minimal_json

        c = SlurmCliClient()
        result = c.sdiag_structured()

        assert result.server_thread_count == 10
        assert result.agent_queue_size == 5
        assert result.schedule_cycle_max is None
        assert result.bf_backfilled_jobs is None
        assert result.schedule_exit_end_job_queue is None
        assert result.bf_exit_end_job_queue is None
        assert result.rpcs_by_message_type_json == "[]"
        assert result.rpcs_by_user_json == "[]"
        mock_reset.assert_called_once()

    @staticmethod
    @pytest.mark.parametrize(
        "raw_bf_active, expected",
        [
            (False, False),
            (True, True),
            (0, False),
            (1, True),
            ("__missing__", None),
            (None, None),
        ],
    )
    @patch.object(SlurmCliClient, "_reset_sdiag_counters")
    @patch("clusterscope.slurm_version")
    @patch("subprocess.check_output")
    def test_parse_sdiag_json_bf_active_variants(
        mock_check_output: MagicMock,
        mock_slurm_version: MagicMock,
        mock_reset: MagicMock,
        raw_bf_active: object,
        expected: object,
    ) -> None:
        """Regression: bf_active must round-trip JSON booleans (true/false),
        defensively coerce numeric 0/1, and stay None when absent or null.
        Catches a future refactor that drops the `is not None` guard and
        turns missing -> False, or that loses the bool() coercion."""
        mock_slurm_version.return_value = (23, 2)

        stats: dict[str, object] = {
            "server_thread_count": 1,
            "agent_queue_size": 0,
            "agent_count": 0,
            "agent_thread_count": 0,
            "dbd_agent_queue_size": 0,
        }
        if raw_bf_active != "__missing__":
            stats["bf_active"] = raw_bf_active
        mock_check_output.return_value = json.dumps({"statistics": stats})

        c = SlurmCliClient()
        result = c.sdiag_structured()

        assert result.bf_active is expected
        mock_reset.assert_called_once()

    @staticmethod
    @patch.object(SlurmCliClient, "_reset_sdiag_counters")
    @patch("clusterscope.slurm_version")
    @patch("subprocess.check_output")
    def test_parse_sdiag_json_with_explicit_null_timestamp_objects(
        mock_check_output: MagicMock,
        mock_slurm_version: MagicMock,
        mock_reset: MagicMock,
    ) -> None:
        """Regression: sdiag can emit explicit `null` for timestamp objects
        (req_time, req_time_start, job_states_ts, bf_when_last_cycle) when
        the cluster has never reset its counters. Earlier code used
        `stats.get(k, {})` which returns None for an explicit null and then
        crashed on `.get("set")`. The fix uses `stats.get(k) or {}`."""
        mock_slurm_version.return_value = (23, 2)

        null_ts_json = json.dumps(
            {
                "statistics": {
                    "server_thread_count": 1,
                    "agent_queue_size": 0,
                    "agent_count": 0,
                    "agent_thread_count": 0,
                    "dbd_agent_queue_size": 0,
                    "req_time": None,
                    "req_time_start": None,
                    "job_states_ts": None,
                    "bf_when_last_cycle": None,
                }
            }
        )
        mock_check_output.return_value = null_ts_json

        c = SlurmCliClient()
        result = c.sdiag_structured()

        assert result.req_time is None
        assert result.req_time_start is None
        assert result.job_states_ts is None
        assert result.bf_when_last_cycle is None
        mock_reset.assert_called_once()


class TestTruncatedNodelist:
    """Tests for the _truncated_nodelist helper that caps oversized nodelists."""

    def test_normal_nodelist_unchanged(self) -> None:
        """Nodelists with <= 1000 entries pass through unchanged."""
        # A small nodelist: "node[001-010]" expands to 10 entries
        result = _truncated_nodelist("node[001-010]")
        assert result is not None
        assert len(result) == 10
        assert result[0] == "node001"
        assert result[-1] == "node010"
        # No "..." marker
        assert "..." not in result

    def test_large_nodelist_truncated(self) -> None:
        """Nodelists with > 1000 entries are truncated to 1000 + '...' marker."""
        # A large nodelist: "h200-[0001-2000]" expands to 2000 entries
        result = _truncated_nodelist("h200-[0001-2000]")
        assert result is not None
        assert len(result) == 1001  # 1000 entries + "..."
        assert result[0] == "h200-0001"
        assert result[999] == "h200-1000"
        assert result[-1] == "..."

    def test_exactly_1000_entries_unchanged(self) -> None:
        """Nodelists with exactly 1000 entries are not truncated."""
        result = _truncated_nodelist("n[0001-1000]")
        assert result is not None
        assert len(result) == 1000
        assert "..." not in result

    def test_empty_nodelist_returns_none(self) -> None:
        """Empty/unparseable nodelists return None."""
        result = _truncated_nodelist("")
        assert result is None
