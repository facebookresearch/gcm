# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable, Mapping

from click.testing import CliRunner
from gcm.exporters.stdout import Stdout

from gcm.monitoring.cli.scontrol import CliObject, main
from gcm.monitoring.clock import Clock
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.monitoring.slurm.client import SlurmClient
from gcm.tests import data
from gcm.tests.fakes import FakeClock

TEST_CLUSTER = "fake_cluster"


class FakeSlurmClient(SlurmClient):
    def scontrol_partition(self) -> Iterable[str]:
        with resources.open_text(data, "sample-scontrol-output.txt") as f:
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

    def format_epilog(self) -> str:
        return ""


def test_cli(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj: CliObject = FakeCliObject()
    expected_scontrol_info = [
        {
            "MaxNodes": -1,
            "PriorityJobFactor": 10,
            "PriorityTier": 10,
            "TotalCPUs": 251200,
            "TotalNodes": 3140,
            "TresCPU": 251200,
            "TresMEM": 1770000000,
            "TresNODE": 3140,
            "TresBILLING": 825408,
            "TresGRESGPU": 22384,
            "TresBillingWeightCPU": 1,
            "TresBillingWeightMEM": 125,
            "TresBillingWeightGRESGPU": 16,
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "Partition": "partition1",
            "QoS": "qos1",
            "Nodes": "node[0201-0272,0281-0932,1069-2468,4000-4455,5025-5028,5041-5316,7456-7735]",
            "PreemptMode": "REQUEUE",
        },
        {
            "MaxNodes": 64,
            "PriorityJobFactor": 1,
            "PriorityTier": 25,
            "TotalCPUs": 141024,
            "TotalNodes": 1469,
            "TresBillingWeightCPU": 2,
            "TresBillingWeightMEM": 250,
            "TresBillingWeightGRESGPU": 32,
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "Partition": "partition2",
            "QoS": "N/A",
            "Nodes": "node[1-855],node[856-1171],node[1172-1320],node[1322-1470]",
            "PreemptMode": "REQUEUE",
        },
        {
            "MaxNodes": -1,
            "PriorityJobFactor": 1,
            "PriorityTier": 1,
            "TotalCPUs": 251200,
            "TotalNodes": 3140,
            "TresCPU": 251200,
            "TresMEM": 1770000000,
            "TresNODE": 3140,
            "TresBILLING": 0,
            "TresGRESGPU": 22384,
            "TresBillingWeightCPU": 0,
            "TresBillingWeightMEM": 0,
            "TresBillingWeightGRESGPU": 0,
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "Partition": "partition3",
            "QoS": "N/A",
            "Nodes": "node[0201-0272,0281-0932,1069-2468,4000-4455,5025-5028,5041-5316,7456-7735]",
            "PreemptMode": "OFF",
        },
    ]

    result = runner.invoke(
        main,
        [
            "--sink=stdout",
            f"--log-folder={tmp_path}",
            "--once",
        ],
        obj=fake_obj,
        catch_exceptions=True,
    )
    lines = result.stdout.strip().split("\n")
    assert json.loads(lines[0]) == expected_scontrol_info
