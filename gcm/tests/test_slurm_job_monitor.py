# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import (
    Any,
    Callable,
    Hashable,
    Iterable,
    List,
    Mapping,
    Optional,
    Type,
    TYPE_CHECKING,
    TypeVar,
)
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from gcm.exporters.stdout import Stdout

from gcm.monitoring.cli.slurm_job_monitor import CliObject, main
from gcm.monitoring.clock import Clock, time_to_time_aware
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.monitoring.slurm.client import SlurmCliClient, SlurmClient
from gcm.monitoring.utils.parsing.stdout import parse_delimited
from gcm.tests import data
from gcm.tests.fakes import FakeClock
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

_TDataclass = TypeVar("_TDataclass")
TEST_CLUSTER = "node"


@dataclass
class Foo:
    foo: str


@dataclass
class FooBar:
    foo: str
    bar: str


@dataclass
class FooBaz:
    foo: str
    baz: str


@dataclass
class FooBarBaz:
    foo: str
    bar: str
    baz: str


@pytest.mark.parametrize(
    "output, schema, expected_header, expected_data",
    [
        (["foo", "hello"], Foo, ["foo"], [["hello"]]),
        (
            ["foo|bar", "hello|world"],
            FooBar,
            ["foo", "bar"],
            [["hello", "world"]],
        ),
        (
            ["foo|bar", "hello|world"],
            FooBarBaz,
            ["foo", "bar"],
            [["hello", "world"]],
        ),
        (
            ["foo|bar|baz", "hello|world|quux"],
            FooBar,
            ["foo", "bar"],
            [["hello", "world"]],
        ),
        (
            ["foo|bar|baz", "hello|world|quux"],
            FooBaz,
            ["foo", "baz"],
            [["hello", "quux"]],
        ),
        (
            ["foo|bar", "hello|world", "bye|earth"],
            FooBar,
            ["foo", "bar"],
            [["hello", "world"], ["bye", "earth"]],
        ),
        (
            ["foo|bar|bar", "hello|world|quux"],
            FooBar,
            ["foo", "bar"],
            [["hello", "world"]],
        ),
        (
            ["foo|bar", "hello|world", "oops", "quick|fox"],
            FooBar,
            ["foo", "bar"],
            [["hello", "world"], ["quick", "fox"]],
        ),
    ],
)
@typechecked
def test_parse_delimited(
    output: List[str],
    schema: Type[_TDataclass],
    expected_header: List[str],
    expected_data: List[List[str]],
) -> None:
    logger = MagicMock()
    header, data = parse_delimited(output, schema, "|", logger)

    assert header == expected_header
    assert list(data) == expected_data


class FakeSlurmClient(SlurmCliClient):
    def squeue(
        self,
        derived_cluster_fetcher: Callable[[Mapping[Hashable, str | int]], str],
        logger: logging.Logger,
        attributes: Optional[dict[Hashable, Any]] = None,
    ) -> Iterable[DataclassInstance]:
        return self._parse_squeue(
            gen_squeue_lines=(
                line.strip()
                for line in resources.files("gcm.tests")
                .joinpath("data/sample-squeue-output.txt")
                .open("r")
            ),
            attributes=attributes,
            derived_cluster_fetcher=derived_cluster_fetcher,
            logger=logging.getLogger(),
        )

    def sinfo(self) -> Iterable[str]:
        with resources.open_text(data, "sample-sinfo-output.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@dataclass
class FakeCliObject:
    clock: Clock = field(default_factory=FakeClock)
    slurm_client: SlurmClient = field(default_factory=FakeSlurmClient)
    registry: Mapping[str, Factory[SinkImpl]] = field(
        default_factory=lambda: {"stdout": Stdout}
    )

    def cluster(self) -> str:
        return TEST_CLUSTER


def test_cli(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj: CliObject = FakeCliObject()
    expected_node_info = [
        {
            "CPUS_ALLOCATED": 0,
            "CPUS_IDLE": 0,
            "CPUS_OTHER": 80,
            "CPUS_TOTAL": 80,
            "MEMORY": 500_000,
            "NUM_GPUS": 8,
            "num_rows": 4,
            "collection_unixtime": FakeClock().unixtime(),
            "NODE_NAME": "node0201",
            "PARTITION": "partition",
            "USER": "root",
            "REASON": "replace",
            "TIMESTAMP": "2022-06-02T05:54:34",
            "ACTIVE_FEATURES": "gen,bldg1,ib4",
            "STATE": "drained*",
            "RESERVATION": "",
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
        },
        {
            "CPUS_ALLOCATED": 0,
            "CPUS_IDLE": 0,
            "CPUS_OTHER": 80,
            "CPUS_TOTAL": 80,
            "MEMORY": 500_000,
            "NUM_GPUS": 8,
            "num_rows": 4,
            "collection_unixtime": FakeClock().unixtime(),
            "NODE_NAME": "node0201",
            "PARTITION": "partition",
            "USER": "root",
            "REASON": "replace",
            "TIMESTAMP": "2022-06-02T05:54:34",
            "ACTIVE_FEATURES": "gen,bldg1,ib4",
            "STATE": "drained*",
            "RESERVATION": "test_reservation",
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
        },
        {
            "CPUS_ALLOCATED": 80,
            "CPUS_IDLE": 0,
            "CPUS_OTHER": 0,
            "CPUS_TOTAL": 80,
            "FREE_MEM": 210_288,
            "MEMORY": 500_000,
            "NUM_GPUS": 8,
            "num_rows": 4,
            "collection_unixtime": FakeClock().unixtime(),
            "NODE_NAME": "node1537",
            "PARTITION": "partition",
            "USER": "Unknown",
            "REASON": "none",
            "TIMESTAMP": "Unknown",
            "ACTIVE_FEATURES": "gen,bldg2,ib4",
            "STATE": "allocated",
            "RESERVATION": "test_reservation",
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
        },
        {
            "CPUS_ALLOCATED": 80,
            "CPUS_IDLE": 0,
            "CPUS_OTHER": 0,
            "CPUS_TOTAL": 80,
            "FREE_MEM": 449_512,
            "MEMORY": 500_000,
            "NUM_GPUS": 2,
            "num_rows": 4,
            "collection_unixtime": FakeClock().unixtime(),
            "NODE_NAME": "node4180",
            "PARTITION": "partition",
            "USER": "Unknown",
            "REASON": "none",
            "TIMESTAMP": "Unknown",
            "ACTIVE_FEATURES": "gen,bldg1,ib1,gpu2",
            "STATE": "allocated",
            "RESERVATION": "test_reservation",
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
        },
    ]
    expected_job_info = [
        {
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "collection_unixtime": FakeClock().unixtime(),
            "GPUS_REQUESTED": 0,
            "MIN_CPUS": 1,
            "MIN_MEMORY": 0,
            "CPUS": 24,
            "NODES": 1,
            "TRES_GPUS_ALLOCATED": 2,
            "TRES_CPU_ALLOCATED": 24,
            "TRES_MEM_ALLOCATED": 0,
            "TRES_NODE_ALLOCATED": 1,
            "TRES_BILLING_ALLOCATED": 112,
            "PRIORITY": 0.00017607258637,
            "JOBID": "45704744",
            "JOBID_RAW": "45704744",
            "NAME": "bash",
            "TIME_LIMIT": "14-00:00:00",
            "COMMAND": "bash",
            "STATE": "RUNNING",
            "USER": "test_user",
            "TIME_LEFT": "13-06:37:11",
            "TIME_USED": "17:22:49",
            "DEPENDENCY": "(null)",
            "START_TIME": time_to_time_aware("2025-04-10T13:44:41"),
            "SUBMIT_TIME": time_to_time_aware("2025-04-10T13:44:39"),
            "ELIGIBLE_TIME": time_to_time_aware("2025-04-10T13:44:39"),
            "ACCRUE_TIME": time_to_time_aware("2025-04-10T13:44:40"),
            "PENDING_TIME": 100,
            "COMMENT": "(null)",
            "PARTITION": "partition",
            "FEATURE": "gpu",
            "REQUEUE": "1",
            "RESERVATION": "",
            "RESTARTCNT": 1,
            "SCHEDNODES": [
                "node1321",
            ],
            "ACCOUNT": "account",
            "QOS": "normal",
            "REASON": "None",
            "PENDING_RESOURCES": "False",
            "NODELIST": ["node1321"],
        },
        {
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "collection_unixtime": FakeClock().unixtime(),
            "GPUS_REQUESTED": 1,
            "MIN_CPUS": 1,
            "MIN_MEMORY": 60000,
            "CPUS": 1,
            "NODES": 1,
            "TRES_GPUS_ALLOCATED": 1,
            "TRES_CPU_ALLOCATED": 1,
            "TRES_MEM_ALLOCATED": 0,
            "TRES_NODE_ALLOCATED": 1,
            "TRES_BILLING_ALLOCATED": 34,
            "PRIORITY": 0.00017546257008,
            "JOBID": "42953390_320",
            "JOBID_RAW": "42953598",
            "NAME": "run1",
            "TIME_LIMIT": "3-00:00:00",
            "COMMAND": "/test/run.sh",
            "STATE": "RUNNING",
            "USER": "test_user",
            "TIME_LEFT": "2-17:56:34",
            "TIME_USED": "6:03:26",
            "DEPENDENCY": "(null)",
            "START_TIME": time_to_time_aware("2025-03-06T21:01:21"),
            "SUBMIT_TIME": time_to_time_aware("2025-03-06T20:59:59"),
            "ELIGIBLE_TIME": time_to_time_aware("2025-03-06T20:59:59"),
            "ACCRUE_TIME": time_to_time_aware("2025-03-06T21:01:00"),
            "PENDING_TIME": 82,
            "COMMENT": "(null)",
            "PARTITION": "partition",
            "FEATURE": "gpu",
            "REQUEUE": "1",
            "RESERVATION": "",
            "RESTARTCNT": 1,
            "SCHEDNODES": [
                "node1303",
            ],
            "ACCOUNT": "account",
            "QOS": "normal",
            "REASON": "None",
            "PENDING_RESOURCES": "False",
            "NODELIST": ["node1303"],
        },
        {
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "collection_unixtime": 1668197951,
            "GPUS_REQUESTED": 8,
            "MIN_CPUS": 80,
            "MIN_MEMORY": 60000,
            "CPUS": 2560,
            "NODES": 32,
            "TRES_GPUS_ALLOCATED": 256,
            "TRES_CPU_ALLOCATED": 2560,
            "TRES_MEM_ALLOCATED": 0,
            "TRES_NODE_ALLOCATED": 32,
            "TRES_BILLING_ALLOCATED": 0,
            "PRIORITY": 5.95580787e-06,
            "JOBID": "42956774_3",
            "JOBID_RAW": "42956774",
            "NAME": "run3",
            "TIME_LIMIT": "3-00:00:00",
            "COMMAND": "/test/run.sh",
            "STATE": "RUNNING",
            "USER": "test_user",
            "TIME_LEFT": "2-23:55:01",
            "TIME_USED": "4:59",
            "DEPENDENCY": "(null)",
            "START_TIME": time_to_time_aware("2025-03-07T04:16:04"),
            "SUBMIT_TIME": time_to_time_aware("2025-03-07T04:15:46"),
            "ELIGIBLE_TIME": time_to_time_aware("2025-03-07T04:15:46"),
            "ACCRUE_TIME": time_to_time_aware("2025-03-07T04:16:03"),
            "PENDING_TIME": 18,
            "COMMENT": "(null)",
            "PARTITION": "partition",
            "ACCOUNT": "account",
            "QOS": "normal",
            "FEATURE": "gpu",
            "REQUEUE": "1",
            "RESERVATION": "",
            "RESTARTCNT": 6,
            "SCHEDNODES": [
                "node1381",
                "node1382",
                "node1383",
            ],
            "REASON": "None",
            "PENDING_RESOURCES": "False",
            "NODELIST": [
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
        },
        {
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "collection_unixtime": FakeClock().unixtime(),
            "GPUS_REQUESTED": 0,
            "MIN_CPUS": 1,
            "MIN_MEMORY": 10500,
            "CPUS": 1,
            "NODES": 1,
            "TRES_GPUS_ALLOCATED": 0,
            "TRES_CPU_ALLOCATED": 1,
            "TRES_MEM_ALLOCATED": 10000,
            "TRES_NODE_ALLOCATED": 1,
            "TRES_BILLING_ALLOCATED": 2,
            "PRIORITY": 0.00018553552222,
            "JOBID": "22783212",
            "JOBID_RAW": "22783212",
            "NAME": "run4",
            "TIME_LIMIT": "1:00:00",
            "COMMAND": "/test/run.sh",
            "STATE": "PENDING",
            "USER": "test_user",
            "TIME_LEFT": "1:00:00",
            "TIME_USED": "0:00",
            "DEPENDENCY": "afterok:22783211_*(failed)",
            "SUBMIT_TIME": time_to_time_aware("2024-01-31T04:06:57"),
            "ELIGIBLE_TIME": "N/A",
            "ACCRUE_TIME": "N/A",
            "PENDING_TIME": 0,
            "COMMENT": "(null)",
            "PARTITION": "partition",
            "ACCOUNT": "account",
            "QOS": "normal",
            "FEATURE": "gpu",
            "REQUEUE": "1",
            "RESERVATION": "",
            "RESTARTCNT": 123,
            "SCHEDNODES": [
                "node1381",
                "node1382",
                "node1383",
            ],
            "REASON": "DependencyNeverSatisfied",
            "PENDING_RESOURCES": "False",
            "START_TIME": "N/A",
        },
        {
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "collection_unixtime": FakeClock().unixtime(),
            "GPUS_REQUESTED": 8,
            "MIN_CPUS": 16,
            "MIN_MEMORY": 1000000,
            "CPUS": 320,
            "NODES": 20,
            "TRES_GPUS_ALLOCATED": 160,
            "TRES_CPU_ALLOCATED": 320,
            "TRES_MEM_ALLOCATED": 1280500,
            "TRES_NODE_ALLOCATED": 20,
            "TRES_BILLING_ALLOCATED": 3040,
            "PRIORITY": 0.00012484216134,
            "JOBID": "42271120_[7-8%1]",
            "JOBID_RAW": "42271120",
            "NAME": "run5",
            "TIME_LIMIT": "3-00:00:00",
            "COMMAND": "/test/run.sh",
            "STATE": "PENDING",
            "USER": "test_user",
            "TIME_LEFT": "3-00:00:00",
            "TIME_USED": "0:00",
            "DEPENDENCY": "(null)",
            "FEATURE": "gpu",
            "SUBMIT_TIME": time_to_time_aware("2025-02-26T15:29:14"),
            "ELIGIBLE_TIME": "N/A",
            "ACCRUE_TIME": "N/A",
            "PENDING_TIME": 0,
            "COMMENT": "(null)",
            "PARTITION": "partition",
            "ACCOUNT": "account",
            "QOS": "normal",
            "REASON": "JobArrayTaskLimit",
            "REQUEUE": "1",
            "RESERVATION": "",
            "RESTARTCNT": 10,
            "SCHEDNODES": [
                "node1381",
                "node1382",
                "node1383",
            ],
            "START_TIME": "N/A",
            "PENDING_RESOURCES": "False",
        },
    ]

    result = runner.invoke(
        main,
        [
            "--sink",
            "stdout",
            f"--log-folder={tmp_path}",
            "--once",
            "--cluster",
            TEST_CLUSTER,
            "--stdout",
        ],
        obj=fake_obj,
        catch_exceptions=False,
    )

    lines = result.stdout.strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[1]) == expected_node_info
    assert json.loads(lines[2]) == expected_job_info
