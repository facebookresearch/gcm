# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class Statvfs:
    cluster: str
    directory: str
    file_system: str
    f_bsize: int
    f_frsize: int
    f_blocks: int
    f_bfree: int
    f_bavail: int
    f_files: int
    f_ffree: int
    f_favail: int
    f_fsid: int
    f_flag: int
    f_namemax: int
