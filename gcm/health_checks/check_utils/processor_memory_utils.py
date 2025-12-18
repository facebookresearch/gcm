# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Mapping, TypedDict


class MemAttrs(TypedDict):
    dimms: int
    total_size_gb: int


# One can store known values for certain machines.
# This enables easier invocation, i.e. for the case of RSC automation.
known_hostname_mem_mappings: Mapping[str, MemAttrs] = {
    "rscadmin": MemAttrs(dimms=16, total_size_gb=1024),
    "rsclearn": MemAttrs(dimms=32, total_size_gb=2048),
    "rsccache": MemAttrs(dimms=8, total_size_gb=512),
    "rsccpu": MemAttrs(dimms=16, total_size_gb=1024),
    "avaadmin": MemAttrs(dimms=16, total_size_gb=1024),
    "avacache": MemAttrs(dimms=8, total_size_gb=512),
    "avalearn": MemAttrs(dimms=32, total_size_gb=2048),
    "avaworker": MemAttrs(dimms=16, total_size_gb=1024),
    "avacpu": MemAttrs(dimms=16, total_size_gb=1024),
}


def get_mem_attributes(hostname: str) -> MemAttrs:
    for key in known_hostname_mem_mappings.keys():
        if hostname.startswith(key):
            return known_hostname_mem_mappings[key]
    raise ValueError(
        "DIMMs and Total size are not of known values. Please provide expected values."
    )
