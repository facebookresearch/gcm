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

    # Slurm's hostlist notation (`g3-129-[057,059,063]`) expanded and re-joined
    # as a comma-separated string. Kept as a string rather than a `list[str]`
    # because sinks flatten list fields into one indexed column per element
    # (`Nodes.0`, `Nodes.1`, ...), which is both unqueryable as a single value
    # and lossy: Scuba caps the columns it keeps per sample, so node lists
    # longer than ~507 entries silently lose their leading elements.
    Nodes: str | None = parsed_field(parser=str)
    node_count: int | None = None
