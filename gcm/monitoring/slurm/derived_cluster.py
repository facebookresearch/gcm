# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from functools import lru_cache
from typing import Hashable, Mapping


@lru_cache(maxsize=1)
def derived_cluster_for_heterogeneous_cluster_v1(
    partition: str,
    cluster: str,
) -> str:
    return f"{cluster}.{partition}" if partition != "" else cluster


def get_derived_cluster(
    data: Mapping[Hashable, str | int],
    heterogeneous_cluster_v1: bool,
    cluster: str,
    get_partition_from_qos: bool = False,
) -> str:
    """
    Computes 'derived_cluster' attribute.

    heterogeneous_cluster_v1:
        Use this flag when multiple types of GPUs are managed by separate partitions, e.g.,
        NVIDIA H100 and H200 GPUs in separate 'h100' and 'h200' partitions.

        This flag when passed will result in the 'derived cluster' attribute being: <cluster_name>.<partition_name>
        For QoS-based commands (sacctmgr_qos) you should also pass get_partition_from_qos as True, this generates the <partition_name> by extracting characters from the QoS Name string up to the first underscore (_) or using all characters if no underscore is present. For example, a QoS named: h100_myqos would result in `derived_cluster = <cluster_name>.h100` .
    """
    if heterogeneous_cluster_v1:
        partition = ""
        # sacctmgr_qos
        if get_partition_from_qos:
            partition = str(data["Name"]).partition("_")[0]
        # sinfo, squeue
        elif "PARTITION" in data:
            partition = str(data["PARTITION"]).strip("*")
        # sacct
        elif "Partition" in data:
            partition = str(data["Partition"])
            # sacct - job steps don't have partition name defined, so try getting it from nodelist
            if partition == "" and "NodeList" in data:
                # assume nodes are named: <partition_name>-<...>
                nodelist = str(data["NodeList"])
                partition = nodelist.split("-")[0]
        # scontrol
        elif "PartitionName" in data:
            partition = str(data["PartitionName"])
        # health_checks
        elif "Node" in data:
            # assume nodes are named: <partition_name>-<...>
            nodename = str(data["Node"])
            partition = nodename.split("-")[0]
        else:
            partition = ""

        # squeue, scontrol
        if "cluster" in data:
            cluster = str(data["cluster"])
        # sinfo
        elif "CLUSTER" in data:
            cluster = str(data["CLUSTER"])
        # sacct
        elif "Cluster" in data:
            cluster = str(data["Cluster"])
        # sacctmgr_qos, health_checks
        else:
            cluster = cluster
        return derived_cluster_for_heterogeneous_cluster_v1(
            partition=partition, cluster=cluster
        )
    return cluster
