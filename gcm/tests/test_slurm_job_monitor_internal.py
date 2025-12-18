# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for Node and Job Scribe Publishing.

These tests post mock data into corresponding testing Scribe Categories.
Results can be verified on both Scribe Dashboard and Scuba table.

Scribe: https://www.internalfb.com/intern/scribe/view/?category=perfpipe_gcm_githubci
Scuba: https://www.internalfb.com/intern/scuba/query/?dataset=gcm_githubci
"""

import logging
import os
import subprocess
from functools import partial
from importlib import resources
from pathlib import Path
from typing import Hashable
from unittest.mock import create_autospec

import pytest
from gcm.exporters.graph_api import GraphAPI
from gcm.monitoring.cli.slurm_job_monitor import as_messages
from gcm.monitoring.clock import ClockImpl
from gcm.monitoring.sink.protocol import DataIdentifier, DataType, SinkAdditionalParams
from gcm.monitoring.slurm.client import SlurmCliClient

from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.schemas.log import Log
from gcm.schemas.slurm.sinfo_node import NodeData
from gcm.tests import data
from gcm.tests.config import Config
from gcm.tests.conftest import report_url

SCRIBE_CATEGORY = "perfpipe_gcm_githubci"
TEST_UNIXTIME = ClockImpl().unixtime()
TEST_CLUSTER = "devfair"
LOGGER_NAME = "test_slurm_job_monitor_e2e"


class TestPublishSLURMJobMonitor:
    @staticmethod
    @report_url(
        (
            "Scuba Node Data",
            "https://fburl.com/scuba/gcm_githubci/kr4tje3a",
        )
    )
    def test_publish_slurm_node_data_scribe(config: Config) -> None:
        fake_popen = create_autospec(subprocess.Popen)
        fake_proc = fake_popen.return_value
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.wait.return_value = 0

        with resources.path(data, "sample-sinfo-output.txt") as p:
            with p.open() as f:
                fake_proc.stdout = f
                c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))
                attributes: dict[Hashable, str | int] = {
                    "cluster": TEST_CLUSTER,
                    "collection_unixtime": TEST_UNIXTIME,
                }
                derived_cluster_fetcher = partial(
                    get_derived_cluster,
                    cluster=TEST_CLUSTER,
                    heterogeneous_cluster_v1=False,
                )
                node_data = Log(
                    ts=int(TEST_UNIXTIME),
                    message=as_messages(
                        schema=NodeData,
                        delimiter="|",
                        lines=c.sinfo(),
                        attributes=attributes,
                        derived_cluster_fetcher=derived_cluster_fetcher,
                        logger=logging.getLogger(),
                    ),
                )
                node_api = GraphAPI(
                    app_secret=config.graph_api_access_token,
                    node_scribe_category=SCRIBE_CATEGORY,
                )
                node_api.write(
                    node_data,
                    additional_params=SinkAdditionalParams(
                        data_type=DataType.LOG, data_identifier=DataIdentifier.NODE
                    ),
                )

    @staticmethod
    @report_url(
        (
            "Scuba Node Data heterogeneous cluster",
            "https://fburl.com/scuba/gcm_githubci/oa5brwvh",
        )
    )
    def test_publish_slurm_node_data_scribe_heterogenenous_cluster(
        config: Config,
    ) -> None:
        fake_popen = create_autospec(subprocess.Popen)
        fake_proc = fake_popen.return_value
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.wait.return_value = 0

        with resources.path(data, "sample-sinfo-output.txt") as p:
            with p.open() as f:
                fake_proc.stdout = f
                c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))
                attributes: dict[Hashable, str | int] = {
                    "cluster": TEST_CLUSTER,
                    "collection_unixtime": TEST_UNIXTIME,
                }
                derived_cluster_fetcher = partial(
                    get_derived_cluster,
                    cluster=TEST_CLUSTER,
                    heterogeneous_cluster_v1=True,
                )
                node_data = Log(
                    ts=int(TEST_UNIXTIME),
                    message=as_messages(
                        schema=NodeData,
                        delimiter="|",
                        lines=c.sinfo(),
                        attributes=attributes,
                        derived_cluster_fetcher=derived_cluster_fetcher,
                        logger=logging.getLogger(),
                    ),
                )
                node_api = GraphAPI(
                    app_secret=config.graph_api_access_token,
                    node_scribe_category=SCRIBE_CATEGORY,
                )
                node_api.write(
                    node_data,
                    additional_params=SinkAdditionalParams(
                        data_type=DataType.LOG, data_identifier=DataIdentifier.NODE
                    ),
                )

    @staticmethod
    @report_url(
        (
            "Scuba Job Data",
            "https://fburl.com/scuba/gcm_githubci/bvwu17c7",
        )
    )
    def test_publish_slurm_job_data_scribe(config: Config) -> None:
        fake_popen = create_autospec(subprocess.Popen)
        fake_proc = fake_popen.return_value
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.wait.return_value = 0

        with resources.path(data, "sample-squeue-output.txt") as p:
            with p.open() as f:
                fake_proc.stdout = f
                c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))
                attributes: dict[Hashable, str | int] = {
                    "cluster": TEST_CLUSTER,
                    "collection_unixtime": TEST_UNIXTIME,
                }
                derived_cluster_fetcher = partial(
                    get_derived_cluster,
                    cluster=TEST_CLUSTER,
                    heterogeneous_cluster_v1=False,
                )
                job_data = Log(
                    ts=int(TEST_UNIXTIME),
                    message=c.squeue(
                        attributes=attributes,
                        derived_cluster_fetcher=derived_cluster_fetcher,
                        logger=logging.getLogger(),
                    ),
                )
                job_api = GraphAPI(
                    app_secret=config.graph_api_access_token,
                    job_scribe_category=SCRIBE_CATEGORY,
                )
                job_api.write(
                    data=job_data,
                    additional_params=SinkAdditionalParams(
                        data_type=DataType.LOG, data_identifier=DataIdentifier.JOB
                    ),
                )

    @staticmethod
    @report_url(
        (
            "Scuba Job Data heterogeneous cluster",
            "https://fburl.com/scuba/gcm_githubci/9ia5srev",
        )
    )
    def test_publish_slurm_job_data_scribe_heterogeneous_cluster(
        config: Config,
    ) -> None:
        fake_popen = create_autospec(subprocess.Popen)
        fake_proc = fake_popen.return_value
        fake_proc.__enter__.return_value = fake_proc
        fake_proc.wait.return_value = 0

        with resources.path(data, "sample-squeue-output.txt") as p:
            with p.open() as f:
                fake_proc.stdout = f
                c = SlurmCliClient(popen=lambda cmd: fake_popen(cmd))
                attributes: dict[Hashable, str | int] = {
                    "cluster": TEST_CLUSTER,
                    "collection_unixtime": TEST_UNIXTIME,
                }
                derived_cluster_fetcher = partial(
                    get_derived_cluster,
                    cluster=TEST_CLUSTER,
                    heterogeneous_cluster_v1=True,
                )
                job_data = Log(
                    ts=int(TEST_UNIXTIME),
                    message=c.squeue(
                        attributes=attributes,
                        derived_cluster_fetcher=derived_cluster_fetcher,
                        logger=logging.getLogger(),
                    ),
                )
                job_api = GraphAPI(
                    app_secret=config.graph_api_access_token,
                    job_scribe_category=SCRIBE_CATEGORY,
                )
                job_api.write(
                    data=job_data,
                    additional_params=SinkAdditionalParams(
                        data_type=DataType.LOG, data_identifier=DataIdentifier.JOB
                    ),
                )

    @staticmethod
    @pytest.mark.skipif(
        "CI" in os.environ, reason="CI machines do not have Slurm installed."
    )
    @pytest.mark.slow
    def test_cli_once(config: Config, tmp_path: Path) -> None:
        """Test the CLI end-to-end using real Slurm commands.

        Since many jobs are probably running at once and we need to make real network
        requests, this test is quite slow (~20 s).
        """

        subprocess.check_call(
            [
                "gcm",
                "slurm_job_monitor",
                "--sink",
                "graph_api",
                "-o",
                f"app_secret={config.graph_api_access_token}",
                "-o",
                f"node_scribe_category={SCRIBE_CATEGORY}",
                "-o",
                f"job_scribe_category={SCRIBE_CATEGORY}",
                "--once",
                "--log-folder",
                str(tmp_path),
            ]
        )
