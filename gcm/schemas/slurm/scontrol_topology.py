# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.monitoring.coerce import maybe_int
from gcm.schemas.dataclass import parsed_field
from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass(kw_only=True)
class ScontrolTopology(DerivedCluster):
    """Schema for scontrol show topo output.

    Supports both block topology (BlockName/BlockIndex/BlockSize) and
    switch topology (SwitchName/Level/LinkSpeed/Switches) formats.
    """

    cluster: str

    BlockName: str | None = parsed_field(parser=str)
    BlockIndex: int | None = parsed_field(parser=maybe_int)
    BlockSize: int | None = parsed_field(parser=maybe_int)

    SwitchName: str | None = parsed_field(parser=str)
    Level: int | None = parsed_field(parser=maybe_int)
    LinkSpeed: int | None = parsed_field(parser=maybe_int)
    Switches: str | None = parsed_field(parser=str)

    Nodes: list[str] | None = None
    node_count: int | None = None
