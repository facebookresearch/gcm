# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import os
import pwd
from pathlib import Path
from typing import Dict, Iterable, Protocol

from gcm.schemas.storage.mount import MountInfo
from gcm.schemas.storage.pure import PureInfo


class StorageClient(Protocol):
    """A low-level Storage related client."""

    def get_all_mount_info(self) -> Iterable[MountInfo]:
        """Get /proc/self/mountinfo data"""

    def get_pure_json(self, path: str, cluster: str) -> Iterable[PureInfo]:
        """Get /private/home/pure/*.json Penguin provided user data"""

    def get_all_symlink_info(self, path: str) -> Dict[Path, Path]:
        """Get a Dict of all Symlinks in the provided path"""


def as_mount_info(line: str) -> MountInfo:
    mount_info = line.split()
    separator_idx = mount_info.index("-")
    return MountInfo(
        mount_id=int(mount_info[0]),
        parent_id=int(mount_info[1]),
        device_id=mount_info[2],
        root=Path(mount_info[3]),
        mount_point=Path(mount_info[4]),
        mount_options=mount_info[5].split(","),
        optional_fields=mount_info[6:separator_idx],
        filesystem_type=mount_info[separator_idx + 1],
        mount_source=mount_info[separator_idx + 2],
        super_options=mount_info[separator_idx + 3].split(","),
    )


def try_get_username(user: int) -> str | None:
    try:
        return pwd.getpwuid(user)[0]
    except KeyError:
        return None


def as_pure_info(line: str, cluster: str) -> PureInfo:
    line_json = json.loads(line)
    return PureInfo(
        user=int(line_json["user"]),
        used_bytes=int(line_json["used"]),
        sample_time=int(line_json["sample_time"]),
        directory=str(Path(line_json["directory"]).as_posix()),
        username=try_get_username(int(line_json["user"])),
        cluster=cluster,
    )


class StorageCliClient(StorageClient):
    def get_all_mount_info(self) -> Iterable[MountInfo]:
        with open("/proc/self/mountinfo", "r") as file:
            for line in file:
                yield as_mount_info(line)

    def get_pure_json(self, path: str, cluster: str) -> Iterable[PureInfo]:
        with open(path, "r") as file:
            for line in file:
                yield as_pure_info(line, cluster)

    def get_all_symlink_info(self, path: str = "/") -> Dict[Path, Path]:
        symlink_dict = {}
        for filename in os.listdir(path):
            filepath = os.path.join(path, filename)
            if os.path.islink(filepath):
                target = os.readlink(filepath)
                symlink_dict[Path(target)] = Path(filepath)
        return symlink_dict
