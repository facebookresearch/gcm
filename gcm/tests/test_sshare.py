# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from importlib import resources
from importlib.resources import as_file, files
from typing import Any, Generator
from unittest.mock import Mock

import pytest
from gcm.monitoring.cli.sshare import collect_sshare
from gcm.monitoring.clock import unixtime_to_pacific_datetime
from gcm.monitoring.slurm.client import SlurmCliClient
from gcm.schemas.log import Log
from gcm.schemas.slurm.sshare import SsharePayload, SshareRow
from gcm.tests import data
from gcm.tests.fakes import FakeClock

TEST_CLUSTER = "test_cluster"


class FakeSlurmClient(SlurmCliClient):

    def sshare(self) -> Generator[str, None, None]:
        with resources.open_text(data, "sample-sshare.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@pytest.fixture(scope="module")
def dataset_contents() -> list[dict[str, Any]]:
    dataset = "sample-sshare-expected.json"
    with as_file(files(data).joinpath(dataset)) as path:
        return json.load(path.open())


def test_collect_sshare(dataset_contents: list[dict[str, Any]]) -> None:
    sink_impl = Mock()

    data_result = collect_sshare(
        clock=FakeClock(),
        cluster=TEST_CLUSTER,
        slurm_client=FakeSlurmClient(),
        heterogeneous_cluster_v1=False,
    )
    log = Log(
        ts=FakeClock().unixtime(),
        message=data_result,
    )
    sink_impl.write(data=log)

    def sshare_iterator() -> Generator[SsharePayload, None, None]:
        for sshare_data in dataset_contents:
            sshare_row = SshareRow(**sshare_data)
            yield SsharePayload(
                ds=unixtime_to_pacific_datetime(FakeClock().unixtime()).strftime(
                    "%Y-%m-%d"
                ),
                collection_unixtime=FakeClock().unixtime(),
                cluster=TEST_CLUSTER,
                derived_cluster=TEST_CLUSTER,
                sshare=sshare_row,
            )

    expected = Log(ts=FakeClock().unixtime(), message=sshare_iterator())
    actual = sink_impl.write.call_args.kwargs
    assert actual["data"].ts == expected.ts
    assert list(actual["data"].message) == list(expected.message)
