# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Hashable, Mapping

import pytest
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from typeguard import typechecked

TEST_CLUSTER = "fake_cluster"
TEST_PARTITION = "fake_partition"
TEST_QOS = "relevantname_qos"


@pytest.mark.parametrize(
    "data, heterogeneous_cluster_v1, cluster, expected",
    [
        (
            {"PARTITION": TEST_PARTITION, "CLUSTER": TEST_CLUSTER},
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"PARTITION": TEST_PARTITION, "CLUSTER": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {"PARTITION": "", "CLUSTER": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
    ],
)
@typechecked
def test_get_derived_cluster_sinfo(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    cluster: str,
    expected: str,
) -> None:
    actual = get_derived_cluster(
        data=data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        cluster=cluster,
    )
    assert actual == expected


@pytest.mark.parametrize(
    "data, heterogeneous_cluster_v1, cluster, expected",
    [
        (
            {"Partition": TEST_PARTITION, "Cluster": TEST_CLUSTER},
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"Partition": TEST_PARTITION, "Cluster": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {"Partition": "", "Cluster": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {
                "Partition": "",
                "NodeList": f"{TEST_PARTITION}-node",
                "Cluster": TEST_CLUSTER,
            },
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {
                "Partition": "",
                "NodeList": f"{TEST_PARTITION}-node[47,86]",
                "Cluster": TEST_CLUSTER,
            },
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {
                "Partition": "",
                "NodeList": f"{TEST_PARTITION}-node[47-50]",
                "Cluster": TEST_CLUSTER,
            },
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
    ],
)
@typechecked
def test_get_derived_cluster_sacct(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    cluster: str,
    expected: str,
) -> None:
    actual = get_derived_cluster(
        data=data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        cluster=cluster,
    )
    assert actual == expected


@pytest.mark.parametrize(
    "data, heterogeneous_cluster_v1, get_partition_from_qos, cluster, expected",
    [
        (
            {"Name": TEST_QOS},
            False,
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"Name": TEST_QOS},
            True,
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"Name": TEST_QOS},
            True,
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + "relevantname",
        ),
    ],
)
@typechecked
def test_get_derived_cluster_sacctmgr_qos(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    get_partition_from_qos: bool,
    cluster: str,
    expected: str,
) -> None:
    actual = get_derived_cluster(
        data=data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        get_partition_from_qos=get_partition_from_qos,
        cluster=cluster,
    )
    assert actual == expected


@pytest.mark.parametrize(
    "data, heterogeneous_cluster_v1, cluster, expected",
    [
        (
            {"PARTITION": TEST_PARTITION, "cluster": TEST_CLUSTER},
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"PARTITION": TEST_PARTITION, "cluster": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {"PARTITION": "", "cluster": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
    ],
)
@typechecked
def test_get_derived_cluster_squeue(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    cluster: str,
    expected: str,
) -> None:
    actual = get_derived_cluster(
        data=data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        cluster=cluster,
    )
    assert actual == expected


@pytest.mark.parametrize(
    "data, heterogeneous_cluster_v1, cluster, expected",
    [
        (
            {"PartitionName": TEST_PARTITION, "cluster": TEST_CLUSTER},
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"PartitionName": TEST_PARTITION, "cluster": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {"PartitionName": "", "cluster": TEST_CLUSTER},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
    ],
)
@typechecked
def test_get_derived_cluster_scontrol(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    cluster: str,
    expected: str,
) -> None:
    actual = get_derived_cluster(
        data=data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        cluster=cluster,
    )
    assert actual == expected


@pytest.mark.parametrize(
    "data, heterogeneous_cluster_v1, cluster, expected",
    [
        (
            {"Node": f"{TEST_PARTITION}-node"},
            False,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
        (
            {"Node": f"{TEST_PARTITION}-node"},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER + "." + TEST_PARTITION,
        ),
        (
            {"Node": ""},
            True,
            TEST_CLUSTER,
            TEST_CLUSTER,
        ),
    ],
)
@typechecked
def test_get_derived_cluster_health_checks(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    cluster: str,
    expected: str,
) -> None:
    actual = get_derived_cluster(
        data=data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        cluster=cluster,
    )
    assert actual == expected
