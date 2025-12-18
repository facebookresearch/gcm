# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from importlib import resources
from typing import Callable, cast, Generator, Mapping

from click.testing import CliRunner
from gcm.exporters.graph_api import GraphAPI

from gcm.monitoring.cli.sacct_running import CliObject, main
from gcm.monitoring.clock import ClockImpl
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.monitoring.slurm.client import SlurmClient
from gcm.monitoring.slurm.constants import SLURM_CLI_DELIMITER
from gcm.tests import data
from gcm.tests.config import Config
from gcm.tests.conftest import report_url

TEST_TIME = ClockImpl().unixtime()
TEST_CLUSTER = "fake_cluster"
SCRIBE_CATEGORY = "perfpipe_gcm_githubci"


class FakeSlurmClient(SlurmClient):
    def sacct_running(self) -> Generator[str, None, None]:
        with resources.open_text(data, "sample-sacct-running-output.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@dataclass
class FakeCliObject:
    clock = ClockImpl()
    slurm_client: SlurmClient = field(default_factory=FakeSlurmClient)
    registry: Mapping[str, Factory[SinkImpl]] = field(
        default_factory=lambda: {"graph_api": cast(Callable[[], SinkImpl], GraphAPI)}
    )

    def cluster(self) -> str:
        return TEST_CLUSTER

    def format_epilog(self) -> str:
        return ""


class TestSacctRunningJobs:
    @staticmethod
    @report_url(
        (
            "Scuba sacct running jobs",
            "https://fburl.com/scuba/gcm_githubci/fu9iumg4",
        )
    )
    def test_sacct_running_jobs(config: Config) -> None:
        fake_obj: CliObject = FakeCliObject()
        runner = CliRunner(mix_stderr=True)

        r = runner.invoke(
            main,
            [
                "--sink",
                "graph_api",
                "--delimiter",
                SLURM_CLI_DELIMITER,
                "-o",
                f"app_secret={config.graph_api_access_token}",
                "-o",
                f"scribe_category={SCRIBE_CATEGORY}",
                "--once",
                "--cluster",
                TEST_CLUSTER,
            ],
            obj=fake_obj,
            catch_exceptions=False,
        )

        assert r.exit_code == 0
        assert r.stdout == ""

    @staticmethod
    @report_url(
        (
            "Scuba sacct running jobs heterogeneous cluster",
            "https://fburl.com/scuba/gcm_githubci/34g7s0qx",
        )
    )
    def test_sacct_running_jobs_heterogenenous_cluster(config: Config) -> None:
        fake_obj: CliObject = FakeCliObject()
        runner = CliRunner(mix_stderr=True)

        r = runner.invoke(
            main,
            [
                "--sink",
                "graph_api",
                "--delimiter",
                SLURM_CLI_DELIMITER,
                "-o",
                f"app_secret={config.graph_api_access_token}",
                "-o",
                f"scribe_category={SCRIBE_CATEGORY}",
                "--once",
                "--heterogeneous-cluster-v1",
                "--cluster",
                TEST_CLUSTER,
            ],
            obj=fake_obj,
            catch_exceptions=False,
        )

        assert r.exit_code == 0
        assert r.stdout == ""
