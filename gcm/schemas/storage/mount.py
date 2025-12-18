# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class MountInfo:
    """https://man7.org/linux/man-pages/man5/proc.5.html"""

    mount_id: int
    parent_id: int
    device_id: str
    root: Path
    mount_point: Path
    mount_options: List[str]
    optional_fields: List[str]
    filesystem_type: str
    mount_source: str
    super_options: List[str]
