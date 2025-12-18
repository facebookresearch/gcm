# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.monitoring.coerce import maybe_int
from gcm.monitoring.slurm.parsing import parse_scontrol_maxnodes, parse_value_from_tres
from gcm.schemas.dataclass import parsed_field
from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass(kw_only=True)
class Scontrol(DerivedCluster):
    cluster: str
    Partition: str = parsed_field(parser=str, field_name="PartitionName")
    MaxNodes: int = parsed_field(parser=parse_scontrol_maxnodes)
    TresCPU: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "cpu"), field_name="TRES"
    )
    TresMEM: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "mem"), field_name="TRES"
    )
    TresNODE: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "node"), field_name="TRES"
    )
    TresBILLING: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "billing"), field_name="TRES"
    )
    TresGRESGPU: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "gres/gpu"), field_name="TRES"
    )
    TresBillingWeightCPU: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "cpu"),
        field_name="TRESBillingWeights",
    )
    TresBillingWeightMEM: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "mem"),
        field_name="TRESBillingWeights",
    )
    TresBillingWeightGRESGPU: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "gres/gpu"),
        field_name="TRESBillingWeights",
    )
    PriorityJobFactor: int | None = parsed_field(parser=maybe_int)
    PriorityTier: int | None = parsed_field(parser=maybe_int)
    TotalCPUs: int | None = parsed_field(parser=maybe_int)
    TotalNodes: int | None = parsed_field(parser=maybe_int)
    QoS: str = parsed_field(parser=str)
    PreemptMode: str = parsed_field(parser=str)
    Nodes: str = parsed_field(parser=str)
