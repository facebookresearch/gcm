# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from functools import partial
from importlib import resources
from unittest.mock import create_autospec, MagicMock

import pytest
from gcm.monitoring.clock import time_to_time_aware
from gcm.monitoring.slurm.client import SlurmCliClient

from gcm.monitoring.slurm.derived_cluster import get_derived_cluster

from gcm.schemas.slurm.sinfo import Sinfo
from gcm.schemas.slurm.sinfo_node import SinfoNode
from gcm.schemas.slurm.squeue import JobData
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
                    MIN_MEMORY=60000,
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
                    MIN_MEMORY=60000,
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
                    MIN_MEMORY=10500,
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
                    MIN_MEMORY=1000000,
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
