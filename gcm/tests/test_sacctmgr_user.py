# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from importlib import resources
from importlib.resources import as_file, files
from typing import Generator, Hashable
from unittest.mock import Mock

import pytest
from gcm.monitoring.cli.sacctmgr_user import collect_user
from gcm.monitoring.clock import unixtime_to_pacific_datetime
from gcm.monitoring.slurm.client import SlurmCliClient
from gcm.schemas.log import Log
from gcm.schemas.slurm.sacctmgr_user import SacctmgrUserPayload
from gcm.tests import data
from gcm.tests.fakes import FakeClock
from typeguard import typechecked


TEST_CLUSTER = "test_cluster"
TEST_DS = "test_ds"


class FakeSlurmClient(SlurmCliClient):

    def sacctmgr_user(self) -> Generator[str, None, None]:
        with resources.open_text(data, "sample-sacctmgr-user.txt") as f:
            for line in f:
                yield line.rstrip("\n")

    def sacctmgr_user_info(self, username: str) -> Generator[str, None, None]:
        with resources.open_text(data, "sample-sacctmgr-user-info.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@pytest.fixture(scope="module")
@typechecked
def dataset_contents() -> list[dict[str, str]]:
    dataset = "sample-sacctmgr-user-expected.json"
    with as_file(files(data).joinpath(dataset)) as path:
        return json.load(path.open())


def test_collect_user(dataset_contents: list[dict[Hashable, str]]) -> None:
    sink_impl = Mock()

    data = collect_user(
        clock=FakeClock(),
        cluster=TEST_CLUSTER,
        slurm_client=FakeSlurmClient(),
        heterogeneous_cluster_v1=False,
    )
    log = Log(
        ts=FakeClock().unixtime(),
        message=data,
    )
    sink_impl.write(data=log)

    def sacctmgr_user_iterator() -> Generator[SacctmgrUserPayload, None, None]:
        for sacctmgr_user in dataset_contents:
            yield SacctmgrUserPayload(
                ds=unixtime_to_pacific_datetime(FakeClock().unixtime()).strftime(
                    "%Y-%m-%d"
                ),
                cluster=TEST_CLUSTER,
                derived_cluster=TEST_CLUSTER,
                sacctmgr_user=sacctmgr_user,
            )

    expected = Log(ts=FakeClock().unixtime(), message=sacctmgr_user_iterator())
    actual = sink_impl.write.call_args.kwargs
    assert actual["data"].ts == expected.ts
    assert list(actual["data"].message) == list(expected.message)
