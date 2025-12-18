# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from importlib import resources
from importlib.resources import as_file, files
from typing import Hashable, Iterable
from unittest.mock import Mock

import pytest
from gcm.monitoring.cli.sacctmgr_qos import collect_qos, to_payload
from gcm.monitoring.clock import unixtime_to_pacific_datetime
from gcm.monitoring.slurm.client import SlurmCliClient
from gcm.schemas.log import Log
from gcm.schemas.slurm.sacctmgr_qos import SacctmgrQosPayload
from gcm.tests import data
from gcm.tests.fakes import FakeClock
from typeguard import typechecked


TEST_CLUSTER = "test_cluster"
TEST_DS = "test_ds"


class FakeSlurmClient(SlurmCliClient):

    def sacctmgr_qos(self) -> Iterable[str]:
        with resources.open_text(data, "sample-sacctmgr-qos.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@pytest.fixture(scope="module")
@typechecked
def dataset_contents() -> list[dict[str, str]]:
    dataset = "sample-sacctmgr-qos-expected.json"
    with as_file(files(data).joinpath(dataset)) as path:
        return json.load(path.open())


@pytest.mark.parametrize(
    "input, expected_payload",
    [
        (
            "project_name|100|00:00:00|project_name_1,project_name_2||cluster|OverPartQOS||1.000000|cpu=190464,gres/gpu=1200,mem=1339200G||||||||||||||||",
            SacctmgrQosPayload(
                ds=TEST_DS,
                cluster=TEST_CLUSTER,
                sacctmgr_qos={
                    "Name": "project_name",
                    "Priority": "100",
                    "GraceTime": "00:00:00",
                    "Preempt": "project_name_1,project_name_2",
                    "PreemptExemptTime": "",
                    "PreemptMode": "cluster",
                    "Flags": "OverPartQOS",
                    "UsageThres": "",
                    "UsageFactor": "1.000000",
                    "GrpTRES": "cpu=190464,gres/gpu=1200,mem=1339200G",
                    "GrpTRESMins": "",
                    "GrpTRESRunMins": "",
                    "GrpJobs": "",
                    "GrpSubmit": "",
                    "GrpWall": "",
                    "MaxTRES": "",
                    "MaxTRESPerNode": "",
                    "MaxTRESMins": "",
                    "MaxWall": "",
                    "MaxTRESPU": "",
                    "MaxJobsPU": "",
                    "MaxSubmitPU": "",
                    "MaxTRESPA": "",
                    "MaxJobsPA": "",
                    "MaxSubmitPA": "",
                    "MinTRES": "",
                },
                derived_cluster=TEST_CLUSTER,
            ),
        ),
    ],
)
def test_to_payload(input: str, expected_payload: SacctmgrQosPayload) -> None:
    fields = [
        "Name",
        "Priority",
        "GraceTime",
        "Preempt",
        "PreemptExemptTime",
        "PreemptMode",
        "Flags",
        "UsageThres",
        "UsageFactor",
        "GrpTRES",
        "GrpTRESMins",
        "GrpTRESRunMins",
        "GrpJobs",
        "GrpSubmit",
        "GrpWall",
        "MaxTRES",
        "MaxTRESPerNode",
        "MaxTRESMins",
        "MaxWall",
        "MaxTRESPU",
        "MaxJobsPU",
        "MaxSubmitPU",
        "MaxTRESPA",
        "MaxJobsPA",
        "MaxSubmitPA",
        "MinTRES",
    ]
    output = to_payload(
        fields, input, TEST_CLUSTER, TEST_DS, heterogeneous_cluster_v1=False
    )

    assert output == expected_payload


def test_collect_qos(dataset_contents: list[dict[Hashable, str]]) -> None:
    sink_impl = Mock()

    data = collect_qos(
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

    def sacctmgr_qos_iterator() -> Iterable[SacctmgrQosPayload]:
        for sacctmgr_qos in dataset_contents:
            yield SacctmgrQosPayload(
                ds=unixtime_to_pacific_datetime(FakeClock().unixtime()).strftime(
                    "%Y-%m-%d"
                ),
                cluster=TEST_CLUSTER,
                derived_cluster=TEST_CLUSTER,
                sacctmgr_qos=sacctmgr_qos,
            )

    expected = Log(ts=FakeClock().unixtime(), message=sacctmgr_qos_iterator())
    actual = sink_impl.write.call_args.kwargs

    assert actual["data"].ts == expected.ts
    assert list(actual["data"].message) == list(expected.message)
