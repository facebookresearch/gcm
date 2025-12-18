# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_blockdev import check_blockdev
from gcm.health_checks.types import ExitCode
from gcm.tests.data import health_checks


@dataclass
class FakeBlockdevCheckImpl:
    smartdata_path: str
    sysfs_path: str

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def read_manifest(self, manifest_file: str) -> Dict[str, Any]:
        with resources.open_text(health_checks, manifest_file) as manifest:
            return json.loads(manifest.read())

    def read_smartdata(self, blockdev: str) -> Dict[str, Any]:
        final_resource = (
            "gcm.tests.data.health_checks.smartctl_dumps" + "." + self.smartdata_path
        )
        with resources.open_text(final_resource, f"{blockdev}.json") as manifest:
            return json.loads(manifest.read())

    def read_sysfs_dir(self, path: str) -> Optional[List[str]]:
        with resources.open_text(health_checks, self.sysfs_path) as manifest:
            data = json.loads(manifest.read())
            dirlist = []
            subfiles = list(filter(lambda x: x.startswith(path), data.keys()))
            for file in subfiles:
                path_len = len(path)
                subdir = file[path_len:].split("/")[1]
                if subdir != "" and subdir not in dirlist:
                    dirlist.append(subdir)
            return dirlist


@pytest.fixture
def blockdev_tester(request: pytest.FixtureRequest) -> FakeBlockdevCheckImpl:
    """Create FakeBlockdevCheckImpl object"""
    return FakeBlockdevCheckImpl(request.param[0], request.param[1])


@pytest.mark.parametrize(
    "blockdev_tester, manifest_file, expected",
    [
        (
            ("learn_good", "learn_good.json"),
            "DGX_A100.json",
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            ("learn_bad_nvme9", "learn_good.json"),
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "has low spare space",
            ),
        ),
        (
            ("learn_missing_smartdata", "learn_good.json"),
            "DGX_A100.json",
            (
                ExitCode.CRITICAL,
                "Unable to read health logs from drive",
            ),
        ),
        (
            ("cache_good", "cache_milan_good.json"),
            "Altus_XE1211_Cache_Milan.json",
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            ("cache_good", "cache_rome_good.json"),
            "Altus_XE1211_Cache_Rome.json",
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            ("cache_slot2_bad_smartdata", "cache_milan_good.json"),
            "Altus_XE1211_Cache_Milan.json",
            (
                ExitCode.CRITICAL,
                "BAD_SMARTDATA",
            ),
        ),
    ],
    indirect=["blockdev_tester"],
)
def test_check_pci(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    blockdev_tester: FakeBlockdevCheckImpl,
    manifest_file: str,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_blockdev,
        f"fair_cluster prolog --log-folder={tmp_path} --manifest_file={manifest_file} --sink=do_nothing",
        obj=blockdev_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
