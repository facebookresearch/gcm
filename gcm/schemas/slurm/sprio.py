# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field, fields
from typing import Any, Callable, cast, overload, TypeVar

from gcm.monitoring.coerce import maybe_float
from gcm.schemas.slurm.derived_cluster import DerivedCluster

T = TypeVar("T")


@overload
def sprio_parsed_field(format_code: str) -> str: ...


@overload
def sprio_parsed_field(format_code: str, parser: Callable[[str], T]) -> T: ...


def sprio_parsed_field(format_code: str, parser: Callable[[str], Any] = str) -> Any:
    """Field with sprio format code and parser metadata.

    Combines format_code (for generating sprio command) with parser
    (for instantiate_dataclass compatibility like parsed_field).
    """
    return cast(
        Any,
        field(
            default=None,
            metadata={"format_code": format_code, "parser": parser},
        ),
    )


@dataclass
class SprioRow:
    """sprio output schema. Maps field names to SLURM format codes.

    Note: sprio only supports -o (format codes), not -O (field names).
    SLURM outputs incorrect headers for some codes:
      %A → "AGE" (should be ASSOC)
      %P → "PARTITION" (should be PARTITION_PRIO)
    We use custom headers to avoid this confusion.

    Uses sprio_parsed_field which is compatible with instantiate_dataclass().
    """

    JOBID: float | None = sprio_parsed_field("%i", parser=maybe_float)
    PARTITION: str | None = sprio_parsed_field("%r")
    USER: str | None = sprio_parsed_field("%u")
    ACCOUNT: str | None = sprio_parsed_field("%o")
    PRIORITY: float | None = sprio_parsed_field("%Y", parser=maybe_float)
    SITE: float | None = sprio_parsed_field("%S", parser=maybe_float)
    AGE: float | None = sprio_parsed_field("%a", parser=maybe_float)
    ASSOC: float | None = sprio_parsed_field("%A", parser=maybe_float)
    FAIRSHARE: float | None = sprio_parsed_field("%F", parser=maybe_float)
    JOBSIZE: float | None = sprio_parsed_field("%J", parser=maybe_float)
    PARTITION_PRIO: float | None = sprio_parsed_field("%P", parser=maybe_float)
    QOSNAME: str | None = sprio_parsed_field("%n")
    QOS: str | None = sprio_parsed_field("%Q")
    NICE: float | None = sprio_parsed_field("%N", parser=maybe_float)


# Auto-generate header and format spec from dataclass fields.
# We define our own headers instead of using sprio's default output,
# which avoids breakage when Slurm upgrades change header text.
SPRIO_HEADER = "|".join(f.name for f in fields(SprioRow))
SPRIO_FORMAT_SPEC = "|".join(f.metadata["format_code"] for f in fields(SprioRow))


@dataclass(kw_only=True)
class SprioPayload(DerivedCluster):
    ds: str
    collection_unixtime: int
    cluster: str
    sprio: SprioRow
