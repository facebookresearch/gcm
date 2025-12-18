# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_storage import check_storage, process_disk_size
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeCheckDiskStorageImpl:
    disk_usage: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.disk_usage

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], "dummy output")

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool:
        return True

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool:
        return True

    def get_fstab_mount_info(
        self, timeout_secs: int, mountpoint: str, logger: logging.Logger
    ) -> Tuple[ShellCommandOut, ShellCommandOut]:
        return FakeShellCommandOut([""], 0, "dummy output"), FakeShellCommandOut(
            [""], 0, "dummy output"
        )

    def get_disk_size(
        self, timeout_secs: int, volume: str, units: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0], "")


@pytest.fixture
def disk_usage_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckDiskStorageImpl:
    """Create FakeCheckStorageImpl object"""
    return FakeCheckDiskStorageImpl(request.param)


pass_disk = FakeShellCommandOut(
    [],
    0,
    """Use% IUse%
       40%    40%""",
)

warn_disk = FakeShellCommandOut(
    [],
    0,
    """Use% IUse%
       82%    82%""",
)

fail_disk = FakeShellCommandOut(
    [],
    0,
    """Use% IUse%
       90%    90%""",
)

error_disk = FakeShellCommandOut(
    [],
    1,
    "",
)

invalid_disk = FakeShellCommandOut(
    [],
    0,
    """Use% IUse%
       -    90%""",
)

invalid_disk_inode = FakeShellCommandOut(
    [],
    0,
    """Use% IUse%
       39%    -""",
)


@pytest.mark.parametrize(
    "disk_usage_tester, expected",
    [
        (pass_disk, (ExitCode.OK, "Disk usage, 40%, is within limits.")),
        (
            fail_disk,
            (
                ExitCode.CRITICAL,
                "Disk usage, 90%, is above critical threshold of 85%",
            ),
        ),
        (
            warn_disk,
            (
                ExitCode.WARN,
                "Disk usage, 82%, is above warning threshold of 80%",
            ),
        ),
        (
            error_disk,
            (
                ExitCode.WARN,
                "disk usage command FAILED to execute. error_code: 1",
            ),
        ),
        (
            invalid_disk,
            (
                ExitCode.WARN,
                "Invalid disk usage output",
            ),
        ),
    ],
    indirect=["disk_usage_tester"],
)
def test_disk_usage(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    disk_usage_tester: FakeCheckDiskStorageImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"disk-usage fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -v /randomFolder --usage-critical-threshold=85 --usage-warning-threshold=80",
        obj=disk_usage_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "disk_usage_tester, expected",
    [
        (pass_disk, (ExitCode.OK, "Disk usage, 40%, is within limits.")),
        (
            fail_disk,
            (
                ExitCode.CRITICAL,
                "Disk usage, 90%, is above critical threshold of 85%",
            ),
        ),
        (
            warn_disk,
            (
                ExitCode.WARN,
                "Disk usage, 82%, is above warning threshold of 80%",
            ),
        ),
        (
            error_disk,
            (
                ExitCode.WARN,
                "disk usage command FAILED to execute. error_code: 1",
            ),
        ),
        (
            invalid_disk_inode,
            (
                ExitCode.WARN,
                "Invalid disk usage output",
            ),
        ),
    ],
    indirect=["disk_usage_tester"],
)
def test_inode_usage(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    disk_usage_tester: FakeCheckDiskStorageImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"disk-usage fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -v /randomFolder --usage-critical-threshold=85 --usage-warning-threshold=80 --inode-check",
        obj=disk_usage_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@dataclass
class FakeCheckMountImpl:
    mount_status: PipedShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return FakeShellCommandOut([""], 0, "dummy output")

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.mount_status

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool:
        return True

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool:
        return True


@pytest.fixture
def mount_tester(request: pytest.FixtureRequest) -> FakeCheckMountImpl:
    """Create FakeCheckStorageImpl object"""
    return FakeCheckMountImpl(request.param)


pass_mount = PipedShellCommandOut([0, 0], "10.37.8.4:/home on /shared type nfs (rw)")

fail_mount = PipedShellCommandOut([0, 1], "")

error_mount = PipedShellCommandOut([1], "Error message")


@pytest.mark.parametrize(
    "mount_tester, expected",
    [
        (
            pass_mount,
            (
                ExitCode.OK,
                "Directory /randomFolder: directory is mounted.",
            ),
        ),
        (
            fail_mount,
            (
                ExitCode.CRITICAL,
                "Directory /randomFolder: directory is not mounted.",
            ),
        ),
        (
            error_mount,
            (
                ExitCode.WARN,
                "mount command FAILED to execute. error_code: 1 output: Error message",
            ),
        ),
    ],
    indirect=["mount_tester"],
)
def test_mounted_directory(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    mount_tester: FakeCheckMountImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"mounted-directory fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -d /randomFolder",
        obj=mount_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@dataclass
class FakeCheckExistanceImpl:
    existance: bool

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return FakeShellCommandOut([""], 0, "dummy output")

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], "dummy output")

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool:
        return self.existance

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool:
        return self.existance

    def get_fstab_mount_info(
        self, timeout_secs: int, mountpoint: str, logger: logging.Logger
    ) -> Tuple[ShellCommandOut, ShellCommandOut]:
        return FakeShellCommandOut([""], 0, "dummy output"), FakeShellCommandOut(
            [""], 0, "dummy output"
        )


@pytest.fixture
def existance_tester(request: pytest.FixtureRequest) -> FakeCheckExistanceImpl:
    """Create FakeCheckStorageImpl object"""
    return FakeCheckExistanceImpl(request.param)


@pytest.mark.parametrize(
    "existance_tester, expected",
    [
        (
            True,
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            False,
            (
                ExitCode.CRITICAL,
                "File /path/randomFile.txt not found",
            ),
        ),
    ],
    indirect=["existance_tester"],
)
def test_file_existance(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    existance_tester: FakeCheckExistanceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"file-exists fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -f /path/randomFile.txt",
        obj=existance_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "existance_tester, expected",
    [
        (
            False,
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            True,
            (
                ExitCode.CRITICAL,
                "File /path/randomFile.txt found",
            ),
        ),
    ],
    indirect=["existance_tester"],
)
def test_file_existance_should_not_exist(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    existance_tester: FakeCheckExistanceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"file-exists fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -f /path/randomFile.txt --should-not-exist",
        obj=existance_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "existance_tester, expected",
    [
        (
            True,
            (
                ExitCode.OK,
                "OK",
            ),
        ),
        (
            False,
            (
                ExitCode.CRITICAL,
                "Directory /path/randomDir not found",
            ),
        ),
    ],
    indirect=["existance_tester"],
)
def test_dir_existance(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    existance_tester: FakeCheckExistanceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"directory-exists fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -d /path/randomDir",
        obj=existance_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@dataclass
class FakeExceptionImpl:
    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        raise ValueError("Some error")

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        raise ValueError("Some error")

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool:
        raise ValueError("Some error")

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool:
        raise ValueError("Some error")

    def get_fstab_mount_info(
        self, timeout_secs: int, mountpoint: str, logger: logging.Logger
    ) -> Tuple[ShellCommandOut, ShellCommandOut]:
        return FakeShellCommandOut([""], 0, "dummy output"), FakeShellCommandOut(
            [""], 0, "dummy output"
        )


def test_file_dir_exception(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    exception_tester = FakeExceptionImpl()
    result = runner.invoke(
        check_storage,
        f"directory-exists fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -d /path/randomDir",
        obj=exception_tester,
    )

    assert result.exit_code == ExitCode.CRITICAL.value
    assert (
        "Checking directory /path/randomDir. Exception Some error was raised"
        in caplog.text
    )

    result = runner.invoke(
        check_storage,
        f"file-exists fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -f /path/randomFile.txt",
        obj=exception_tester,
    )

    assert result.exit_code == ExitCode.CRITICAL.value
    assert (
        "Checking file /path/randomFile.txt. Exception Some error was raised"
        in caplog.text
    )


@dataclass
class FakeCheckMountpointImpl:
    mountpoint: Tuple[ShellCommandOut, ShellCommandOut]

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return FakeShellCommandOut([""], 0, "dummy output")

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], "dummy output")

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool:
        return True

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool:
        return True

    def get_fstab_mount_info(
        self, timeout_secs: int, mountpoint: str, logger: logging.Logger
    ) -> Tuple[ShellCommandOut, ShellCommandOut]:
        return self.mountpoint


@pytest.fixture
def mountpoint_tester(request: pytest.FixtureRequest) -> FakeCheckMountpointImpl:
    """Create FakeCheckMountpointImpl object"""
    return FakeCheckMountpointImpl(request.param)


pass_check_mountpoint = (
    FakeShellCommandOut(
        [],
        0,
        "/checkpoint/a\n/checkpoint/b\n",
    ),
    FakeShellCommandOut(
        [],
        0,
        "/checkpoint/a\n/checkpoint/b\n",
    ),
)
fail_check_mountpoint = (
    FakeShellCommandOut(
        [],
        0,
        "/checkpoint/a\n/checkpoint/b\n",
    ),
    FakeShellCommandOut(
        [],
        0,
        "/checkpoint/a\n",
    ),
)
error_checkmountpoint = (
    FakeShellCommandOut([], 2, "Error1"),
    FakeShellCommandOut([], 3, "Error2"),
)


@pytest.mark.parametrize(
    "mountpoint_tester, expected",
    [
        (
            pass_check_mountpoint,
            (
                ExitCode.OK,
                "fstab and mounts have the same entries",
            ),
        ),
        (
            fail_check_mountpoint,
            (
                ExitCode.CRITICAL,
                "the following dirs are not mounted: ['/checkpoint/b']",
            ),
        ),
        (
            error_checkmountpoint,
            (
                ExitCode.WARN,
                "awk command failed for check mountpoint",
            ),
        ),
    ],
    indirect=["mountpoint_tester"],
)
def test_check_mountpoint(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    mountpoint_tester: FakeCheckMountpointImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_storage,
        f"check-mountpoint fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --mountpoint=/checkpoint/",
        obj=mountpoint_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@dataclass
class FakeDiskSizeImpl:
    def get_disk_size(
        self, timeout_secs: int, volume: str, units: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        raise NotImplementedError


@pytest.mark.parametrize(
    "value, actual_value, expected_result",
    [
        (1, "2T", ExitCode.OK),
        (3, "2T", ExitCode.CRITICAL),
    ],
)
def test_disk_size(
    tmp_path: Path,
    value: int,
    actual_value: str,
    expected_result: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_shell_command(
        timeout_secs: int, volume: str, units: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], actual_value)

    args = f"disk-size fair_cluster prolog --log-folder={tmp_path} --volume=/dev/sda3 --operator='>' --value={value} --size-unit=T --sink=do_nothing"

    obj = FakeDiskSizeImpl()
    with patch.object(obj, "get_disk_size", side_effect=mock_shell_command):
        result = runner.invoke(check_storage, args, obj=obj)

    assert result.exit_code == expected_result.value


@pytest.mark.parametrize(
    "output, operator, expected_value, expected_exit_code",
    [
        ("2T", ">", 1, ExitCode.OK),
        ("2T", ">", 3, ExitCode.CRITICAL),
        ("3T", "<", 1, ExitCode.CRITICAL),
        ("3T", "<", 4, ExitCode.OK),
        ("3T", "=", 3, ExitCode.OK),
        ("3T", "<=", 4, ExitCode.OK),
        ("3T", ">=", 2, ExitCode.OK),
    ],
)
def test_disk_size_permutations(
    tmp_path: Path,
    output: str,
    operator: str,
    expected_value: int,
    expected_exit_code: ExitCode,
) -> None:
    exit_code, _ = process_disk_size(
        output=output,
        error_codes=[0, 0],
        operator=operator,
        expected_value=expected_value,
    )
    assert exit_code == expected_exit_code
