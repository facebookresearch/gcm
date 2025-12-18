# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.monitoring.coerce import maybe_int
from gcm.monitoring.slurm.parsing import (
    parse_cpus_alloc,
    parse_cpus_idle,
    parse_cpus_other,
    parse_cpus_total,
    parse_gres,
)
from gcm.schemas.dataclass import parsed_field
from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass
class SinfoNode:
    name: str
    gres: str
    gres_used: str
    total_cpus: int
    alloc_cpus: int
    state: str
    partition: str


@dataclass(kw_only=True)
class NodeData(DerivedCluster):
    num_rows: int
    collection_unixtime: int
    cluster: str
    NODE_NAME: str = parsed_field(parser=str, field_name="NODELIST")
    PARTITION: str = parsed_field(parser=str)
    CPUS_ALLOCATED: int = parsed_field(
        parser=parse_cpus_alloc, field_name="CPUS(A/I/O/T)"
    )
    CPUS_IDLE: int = parsed_field(parser=parse_cpus_idle, field_name="CPUS(A/I/O/T)")
    CPUS_OTHER: int = parsed_field(parser=parse_cpus_other, field_name="CPUS(A/I/O/T)")
    CPUS_TOTAL: int = parsed_field(parser=parse_cpus_total, field_name="CPUS(A/I/O/T)")
    FREE_MEM: int | None = parsed_field(parser=maybe_int)
    MEMORY: int | None = parsed_field(parser=maybe_int)
    NUM_GPUS: int = parsed_field(parser=parse_gres, field_name="GRES")
    USER: str = parsed_field(parser=str)
    REASON: str = parsed_field(parser=str)
    TIMESTAMP: str = parsed_field(parser=str)
    ACTIVE_FEATURES: str = parsed_field(parser=str)
    STATE: str = parsed_field(parser=str)
    RESERVATION: str = parsed_field(parser=str)
