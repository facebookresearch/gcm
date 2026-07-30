# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable, Mapping, Protocol

from click.testing import CliRunner
from gcm.exporters.stdout import Stdout

from gcm.monitoring.cli.scontrol_topology import main
from gcm.monitoring.clock import Clock
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.tests import data
from gcm.tests.fakes import FakeClock

TEST_CLUSTER = "fake_cluster"


class ScontrolTopologyClient(Protocol):
    def scontrol_topology(self) -> Iterable[str]: ...


class FakeSlurmClientBlock:
    def scontrol_topology(self) -> Iterable[str]:
        with resources.open_text(
            data, "sample-scontrol-show-topo-block-output.txt"
        ) as f:
            for line in f:
                yield line.rstrip("\n")


class FakeSlurmClientSwitch:
    def scontrol_topology(self) -> Iterable[str]:
        with resources.open_text(
            data, "sample-scontrol-show-topo-switch-output.txt"
        ) as f:
            for line in f:
                yield line.rstrip("\n")


@dataclass
class FakeCliObject:
    clock: Clock = field(default_factory=FakeClock)
    slurm_client: ScontrolTopologyClient = field(default_factory=FakeSlurmClientBlock)
    registry: Mapping[str, Factory[SinkImpl]] = field(
        default_factory=lambda: {"stdout": Stdout}
    )

    def cluster(self) -> str:
        return TEST_CLUSTER

    def format_epilog(self) -> str:
        return ""


def test_cli_block_topology(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj = FakeCliObject(slurm_client=FakeSlurmClientBlock())
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

    assert result.exit_code == 0, result.stderr
    lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
    parsed = json.loads(lines[0])

    assert parsed[0]["cluster"] == TEST_CLUSTER
    assert parsed[0]["BlockName"] == "block_DH1-062-US-EAST-04B"
    assert parsed[0]["BlockIndex"] == 0
    assert parsed[0]["BlockSize"] == 18
    assert parsed[0]["Nodes"] == ["g3-129-057", "g3-129-059", "g3-129-063"]
    assert parsed[0]["node_count"] == 3
    assert "SwitchName" not in parsed[0]

    assert parsed[2]["BlockName"] == "block_DH1-067-US-EAST-04B"
    assert parsed[2]["BlockIndex"] == 3
    assert parsed[2]["Nodes"] == [
        "g3-129-235",
        "g3-129-237",
        "g3-130-001",
        "g3-130-003",
    ]
    assert parsed[2]["node_count"] == 4


def test_cli_switch_topology(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj = FakeCliObject(slurm_client=FakeSlurmClientSwitch())
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

    assert result.exit_code == 0, result.stderr
    lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
    parsed = json.loads(lines[0])

    assert parsed[0]["SwitchName"] == "cpu"
    assert parsed[0]["Level"] == 0
    assert parsed[0]["LinkSpeed"] == 1
    assert parsed[0]["Nodes"] == ["cpu-000-109", "cpu-002-219", "cpu-003-040"]
    assert parsed[0]["node_count"] == 3
    assert "BlockName" not in parsed[0]

    assert parsed[1]["SwitchName"] == "h100"
    assert parsed[1]["Nodes"] == ["h100-008-154", "h100-236-009"]
    assert parsed[1]["node_count"] == 2

    assert parsed[2]["SwitchName"] == "spine-use2-az3-0"
    assert parsed[2]["Level"] == 1
    assert parsed[2]["Switches"] == "h100"

    assert parsed[3]["SwitchName"] == "data-transfer"
    assert parsed[3]["node_count"] == 0
