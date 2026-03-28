# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from importlib import resources
from importlib.resources import as_file, files
from typing import Any, Generator
from unittest.mock import Mock

import pytest
from gcm.monitoring.cli.sprio import collect_sprio
from gcm.monitoring.clock import unixtime_to_pacific_datetime
from gcm.monitoring.slurm.client import SlurmCliClient
from gcm.schemas.log import Log
from gcm.schemas.slurm.sprio import SprioPayload, SprioRow
from gcm.tests import data
from gcm.tests.fakes import FakeClock

TEST_CLUSTER = "test_cluster"
TEST_DS = "test_ds"


class FakeSlurmClient(SlurmCliClient):

    def sprio(self) -> Generator[str, None, None]:
        with resources.open_text(data, "sample-sprio.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@pytest.fixture(scope="module")
def dataset_contents() -> list[dict[str, Any]]:
    dataset = "sample-sprio-expected.json"
    with as_file(files(data).joinpath(dataset)) as path:
        return json.load(path.open())


def test_collect_sprio(dataset_contents: list[dict[str, Any]]) -> None:
    sink_impl = Mock()

    data_result = collect_sprio(
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

    def sprio_iterator() -> Generator[SprioPayload, None, None]:
        for sprio_data in dataset_contents:
            sprio_row = SprioRow(**sprio_data)
            yield SprioPayload(
                ds=unixtime_to_pacific_datetime(FakeClock().unixtime()).strftime(
                    "%Y-%m-%d"
                ),
                collection_unixtime=FakeClock().unixtime(),
                cluster=TEST_CLUSTER,
                derived_cluster=TEST_CLUSTER,
                sprio=sprio_row,
            )

    expected = Log(ts=FakeClock().unixtime(), message=sprio_iterator())
    actual = sink_impl.write.call_args.kwargs
    assert actual["data"].ts == expected.ts
    assert list(actual["data"].message) == list(expected.message)
