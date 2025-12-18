# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from importlib import resources
from pathlib import Path
from typing import Final, Iterable, List

import pytest

from gcm.monitoring.cli.storage import as_statvfs_messages
from gcm.monitoring.storage import as_mount_info, MountInfo
from gcm.schemas.storage.statvfs import Statvfs
from gcm.tests import data
from typeguard import typechecked

TEST_CLUSTER = "test_cluster"

SAMPLE_STATVFS_DICT: Final = {
    "f_bsize": 524288,
    "f_frsize": 524288,
    "f_blocks": 346030080,
    "f_bfree": 10457532,
    "f_bavail": 10457532,
    "f_files": 354334801920,
    "f_ffree": 10708512400,
    "f_favail": 10708512400,
    "f_fsid": 0,
    "f_flag": 4096,
    "f_namemax": 255,
}


@pytest.mark.parametrize(
    "value, expected",
    [
        (
            "1299 29 0:25 /snapd/ns /run/snapd/ns rw,nosuid,nodev,noexec,relatime - tmpfs tmpfs rw,size=52826344k,mode=755",
            MountInfo(
                mount_id=1299,
                parent_id=29,
                device_id="0:25",
                root=Path("/snapd/ns"),
                mount_point=Path("/run/snapd/ns"),
                mount_options=["rw", "nosuid", "nodev", "noexec", "relatime"],
                optional_fields=[],
                filesystem_type="tmpfs",
                mount_source="tmpfs",
                super_options=["rw", "size=52826344k", "mode=755"],
            ),
        ),
        (
            "24 1 259:2 / / rw,relatime shared:1 main:1 - ext4 /dev/root rw,discard",
            MountInfo(
                mount_id=24,
                parent_id=1,
                device_id="259:2",
                root=Path("/"),
                mount_point=Path("/"),
                mount_options=["rw", "relatime"],
                optional_fields=["shared:1", "main:1"],
                filesystem_type="ext4",
                mount_source="/dev/root",
                super_options=["rw", "discard"],
            ),
        ),
    ],
)
@typechecked
def test_as_mount_info(value: str, expected: MountInfo) -> None:
    assert as_mount_info(value) == expected


def fake_mount(path: str) -> Iterable[MountInfo]:
    with resources.open_text(data, path) as f:
        for line in f:
            yield as_mount_info(line)


@pytest.mark.parametrize(
    "cluster, pattern, mounts, expect",
    [
        (
            TEST_CLUSTER,
            "^/logs.*$|^/public$",
            "sample-proc-self-mountinfo-output.txt",
            [
                Statvfs(
                    f_bsize=524288,
                    f_frsize=524288,
                    f_blocks=346030080,
                    f_bfree=10457532,
                    f_bavail=10457532,
                    f_files=354334801920,
                    f_ffree=10708512400,
                    f_favail=10708512400,
                    f_fsid=0,
                    f_flag=4096,
                    f_namemax=255,
                    cluster=TEST_CLUSTER,
                    directory="/logs",
                    file_system="node101:/syslog",
                ),
                Statvfs(
                    f_bsize=524288,
                    f_frsize=524288,
                    f_blocks=346030080,
                    f_bfree=10457532,
                    f_bavail=10457532,
                    f_files=354334801920,
                    f_ffree=10708512400,
                    f_favail=10708512400,
                    f_fsid=0,
                    f_flag=4096,
                    f_namemax=255,
                    cluster=TEST_CLUSTER,
                    directory="/public",
                    file_system="node101:/public",
                ),
            ],
        ),
    ],
)
def test_as_statvfs_messages(
    pattern: str, cluster: str, mounts: str, expect: List[Statvfs]
) -> None:
    fake_statvfs_info = as_statvfs_messages(
        statvfs_pattern=pattern,
        cluster=cluster,
        lines=fake_mount(mounts),
        get_statvfs=lambda _: SAMPLE_STATVFS_DICT,
        symlink_mapping=None,
    )
    res = list(fake_statvfs_info)
    assert res == expect
