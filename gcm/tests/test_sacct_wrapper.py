# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
from datetime import datetime, timedelta
from functools import partial
from importlib.resources import as_file, files
from itertools import zip_longest
from pathlib import Path
from typing import Callable, cast, Generator, List, Optional, Set, Tuple, Type, Union

import pytest
from click.testing import CliRunner

from gcm.monitoring.cli.sacct_wrapper import (
    filter_sacct_lines,
    filter_sacct_lines_batched,
    filter_sacct_lines_one_by_one,
    get_patched_sacct_cmd,
    get_sacct_lines,
    main,
    should_patch_sacct_cmd,
    strip_non_sacct_args,
    TFilterCallable,
)
from gcm.monitoring.date import ClosedInterval
from gcm.monitoring.slurm.constants import SLURM_CLI_DELIMITER
from gcm.tests import data
from pytest_mock import MockerFixture
from pytest_subprocess import FakeProcess


@pytest.fixture(scope="module")
def dataset_path() -> Generator[Path, None, None]:
    dataset = "sample-sacct-output-midnight-edge-case.txt"
    with as_file(files(data).joinpath(dataset)) as path:
        yield path


@pytest.fixture(scope="module")
def dataset_contents(dataset_path: Path) -> Generator[str, None, None]:
    with dataset_path.open() as f:
        yield f.read()


@pytest.fixture(scope="module")
def small_dataset_path() -> Generator[Path, None, None]:
    dataset = "sample-sacct-output-midnight-edge-case-small.txt"
    with as_file(files(data).joinpath(dataset)) as path:
        yield path


@pytest.fixture(scope="module")
def small_dataset_expected_path() -> Generator[Path, None, None]:
    dataset = "sample-sacct-output-midnight-edge-case-small-expected.txt"
    with as_file(files(data).joinpath(dataset)) as path:
        yield path


@pytest.mark.parametrize(
    "filter_impl",
    [
        partial(
            filter_sacct_lines_one_by_one,
            interval=ClosedInterval(
                lower=datetime.fromisoformat("2021-04-07T00:00:00").astimezone(),
                upper=datetime.fromisoformat("2021-04-07T23:59:59").astimezone(),
            ),
        ),
        partial(
            filter_sacct_lines_batched,
            interval=ClosedInterval(
                lower=datetime.fromisoformat("2021-04-07T00:00:00").astimezone(),
                upper=datetime.fromisoformat("2021-04-07T23:59:59").astimezone(),
            ),
        ),
    ],
)
def test_filter_sacct_lines_small(
    small_dataset_path: Path,
    small_dataset_expected_path: Path,
    filter_impl: TFilterCallable,
) -> None:
    with (
        small_dataset_path.open() as f,
        small_dataset_expected_path.open() as f_expected,
    ):
        stdout = get_sacct_lines(f, "|")
        filtered = filter_sacct_lines(
            stdout,
            filter_impl=filter_impl,
            delimiter="|",
            has_header=True,
        )

        assert list(filtered) == f_expected.read().strip().split("\n")


def test_filter_sacct_lines(dataset_path: Path) -> None:
    pattern = re.compile(r"2021-04-08")
    with dataset_path.open() as f1, dataset_path.open() as f2:
        stdout = get_sacct_lines(f1, "|")
        filtered = filter_sacct_lines(
            stdout,
            filter_impl=partial(
                filter_sacct_lines_one_by_one,
                interval=ClosedInterval(
                    upper=datetime.fromisoformat("2021-04-07T23:59:59").astimezone()
                ),
            ),
            delimiter="|",
            has_header=True,
        )

        assert not any(pattern.search(f) for f in filtered)
        assert any(pattern.search(line) for line in f2)


def test_filter_sacct_lines_batched(dataset_path: Path) -> None:
    pattern = re.compile(r"2021-04-08")
    with dataset_path.open() as f1, dataset_path.open() as f2:
        stdout = get_sacct_lines(f1, "|")
        filtered = filter_sacct_lines(
            stdout,
            filter_impl=partial(
                filter_sacct_lines_batched,
                interval=ClosedInterval(
                    upper=datetime.fromisoformat("2021-04-07T23:59:59").astimezone()
                ),
            ),
            delimiter="|",
            has_header=True,
        )

        assert not any(pattern.search(f) for f in filtered)
        assert any(pattern.search(line) for line in f2)


def test_filter_sacct_lines_batched_eq_unbatched(dataset_path: Path) -> None:
    with dataset_path.open() as f1, dataset_path.open() as f2:
        endtime = datetime.fromisoformat("2021-04-07T23:59:59").astimezone()
        stdout1 = get_sacct_lines(f1, "|")
        stdout2 = get_sacct_lines(f2, "|")
        filtered_unbatched = filter_sacct_lines(
            stdout1,
            filter_impl=partial(
                filter_sacct_lines_one_by_one, interval=ClosedInterval(upper=endtime)
            ),
            delimiter="|",
            has_header=True,
        )
        filtered_batched = filter_sacct_lines(
            stdout2,
            filter_impl=partial(
                filter_sacct_lines_batched, interval=ClosedInterval(upper=endtime)
            ),
            delimiter="|",
            has_header=True,
        )

        assert all(
            unbatched_line == batched_line
            for unbatched_line, batched_line in zip_longest(
                filtered_unbatched, filtered_batched
            )
        )


@pytest.mark.parametrize(
    "file1, file2",
    [
        ("sample-sacct-one-multiline.txt", "sample-sacct-one-multiline-expected.txt"),
        (
            "sample-sacct-fake-line-break.txt",
            "sample-sacct-fake-line-break-expected.txt",
        ),
        (
            "sample-sacct-multiple-multiline.txt",
            "sample-sacct-multiple-multiline-expected.txt",
        ),
        (
            "sample-sacct-one-multiline-expected.txt",
            "sample-sacct-one-multiline-expected.txt",
        ),  # no postprocessing needed
    ],
)
def test_get_sacct_lines(file1: str, file2: str) -> None:
    with (
        as_file(files(data).joinpath(file1)) as path1,
        as_file(files(data).joinpath(file2)) as path2,
    ):
        with open(path1) as f, path2.open() as f_expected:
            iter = get_sacct_lines(f, delimiter=SLURM_CLI_DELIMITER)

            assert "".join(list(iter)) == f_expected.read()


@pytest.mark.parametrize(
    "sacct_args",
    [("-P",), ("--parsable2",)],
)
@pytest.mark.parametrize(
    "starttime, endtime",
    [
        (datetime.now(), datetime.now()),
        (None, datetime.now()),
        (datetime.now(), None),
    ],
)
@pytest.mark.parametrize(
    "states",
    [
        ["failed", "completed", "cancelled", "timeout"],
        ["F", "CD", "CA", "TO"],
        ["FAILED", "cd", "CANCELLED", "to"],
    ],
)
def test_should_patch_sacct_cmd(
    sacct_args: Tuple[str],
    starttime: Optional[datetime],
    endtime: Optional[datetime],
    states: List[str],
) -> None:
    assert should_patch_sacct_cmd(sacct_args, starttime, endtime, states)


@pytest.mark.parametrize(
    "sacct_args, starttime, endtime",
    [
        (tuple(), None, None),
        (("-h",), datetime.now(), datetime.now()),
        (("--help",), datetime.now(), datetime.now()),
        (
            ("-u", "user"),
            datetime.now(),
            datetime.now(),
        ),  # some set of non-help args which isn't -P or --parsable2
    ],
)
@pytest.mark.parametrize("states", [[], ["running"], ["RUNNING"], ["r"], ["R"]])
def test_not_should_patch_sacct_cmd(
    sacct_args: Tuple[str],
    starttime: Optional[datetime],
    endtime: Optional[datetime],
    states: List[str],
) -> None:
    assert not should_patch_sacct_cmd(sacct_args, starttime, endtime, states)


@pytest.mark.parametrize(
    "sacct_args, starttime, fmt_list, start_time_slack, other_extensions, expected",
    [
        (
            ("-P", "-u", "user"),
            datetime.fromisoformat("2020-01-01T00:00:00"),
            ["jobid"],
            timedelta(minutes=2),
            None,
            [
                "sacct",
                "-P",
                "-u",
                "user",
                "-o",
                "jobid,end",
                "-S",
                "2019-12-31T23:58:00",
            ],
        ),
        (
            ("-P",),
            datetime.fromisoformat("2020-01-01T12:00:00"),
            ["jobid"],
            timedelta(minutes=2),
            None,
            [
                "sacct",
                "-P",
                "-o",
                "jobid,end",
                "-S",
                "2020-01-01T11:58:00",
            ],
        ),
        (
            ("-P",),
            datetime.fromisoformat("2020-01-01T12:00:00"),
            ["jobid", "jobname"],
            timedelta(minutes=2),
            None,
            [
                "sacct",
                "-P",
                "-o",
                "jobid,jobname,end",
                "-S",
                "2020-01-01T11:58:00",
            ],
        ),
        (
            ("-P",),
            datetime.fromisoformat("2020-01-01T12:00:00"),
            ["jobid"],
            timedelta(minutes=2),
            lambda extension: extension.extend(["-E", "2020-01-01T13:00:00"]),
            [
                "sacct",
                "-P",
                "-E",
                "2020-01-01T13:00:00",
                "-o",
                "jobid,end",
                "-S",
                "2020-01-01T11:58:00",
            ],
        ),
        # TODO: daylight savings
    ],
)
def test_get_patched_sacct_cmd(
    sacct_args: Tuple[str],
    starttime: Optional[datetime],
    fmt_list: List[str],
    start_time_slack: timedelta,
    other_extensions: Optional[Callable[[List[str]], None]],
    expected: List[str],
) -> None:
    assert (
        get_patched_sacct_cmd(
            sacct_args,
            starttime,
            fmt_list,
            start_time_slack=start_time_slack,
            other_extensions=other_extensions,
        )
        == expected
    )


@pytest.mark.parametrize(
    "cb, exc_cls",
    [
        (lambda: get_patched_sacct_cmd(tuple(), None, []), ValueError),  # type: ignore[arg-type]
        (
            lambda: get_patched_sacct_cmd(
                tuple(), None, ["jobid"], start_time_slack=timedelta(minutes=-2)  # type: ignore[arg-type]
            ),
            ValueError,
        ),
    ],
)
def test_get_patched_sacct_cmd_bad(
    cb: Callable[[], None],
    exc_cls: Type[Exception],
) -> None:
    with pytest.raises(exc_cls):
        cb()


@pytest.mark.parametrize(
    "args",
    [
        ["-h"],
        ["-u", "user"],
        ["-a"],
        # --states is not given
        [
            "-P",
            "-S",
            "2021-04-07T23:57:00",
            "-E",
            "2021-04-07T23:59:59",
            "-a",
            "-o",
            "jobid,state",
        ],
    ],
)
def test_cli_no_patch(
    fake_process: FakeProcess,
    args: List[str],
    mocker: MockerFixture,
    dataset_contents: str,
) -> None:
    """Exercise the CLI for cases where we shouldn't patch `sacct` at all."""
    fake_process.pass_command(["date", fake_process.any()])
    # https://github.com/aklajnert/pytest-subprocess/issues/40
    fake_process.keep_last_process(True)

    # we shouldn't call this function, so make it throw and assert that it wasn't
    # called below
    mock = mocker.patch("gcm.monitoring.cli.sacct_wrapper.get_patched_sacct_cmd")
    mock.side_effect = RuntimeError

    cmd = ("sacct", *args)
    fake_process.register_subprocess(
        # cast() because https://github.com/aklajnert/pytest-subprocess/issues/41
        cmd,
        stdout=cast(List[Union[str, bytes]], dataset_contents.split("\n")),
    )
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(main, args)

    assert result.exit_code == 0
    assert fake_process.call_count(cmd) == 1
    assert not mock.called


@pytest.mark.parametrize(
    "args, expected_args",
    [
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:57:00",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "-s",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-a",
                "-o",
                "jobid,state",
            ],
            [
                "-P",
                "-a",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:00:00",
                "-S",
                "2021-04-07T23:57:00",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "-s",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:57:00",
                "-E",
                "2021-04-07T23:58:59",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "-s",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:57:00",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state",
                "--delimiter",
                ",",
                "--delimiter",
                "|",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:57:00",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state",
                "-o",
                "jobname",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,state,jobname,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:57:00",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,jobname,partition,account,alloccpus,state,exitcode,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        # patched command should strip UTC offsets
        (
            [
                "-P",
                "-S",
                "2021-04-07T23:57:00-07:00",
                "-E",
                "2021-04-07T23:59:59-07:00",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,jobname,partition,account,alloccpus,state,exitcode,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
        # patched command should convert to local time and strip the UTC offset
        (
            [
                "-P",
                "-S",
                "2021-04-08T06:57:00+00:00",
                "-E",
                "2021-04-08T06:59:59+00:00",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
            ],
            [
                "-P",
                "-E",
                "2021-04-07T23:59:59",
                "--delimiter",
                "|",
                "--state",
                "out_of_memory,resizing,timeout,cancelled,revoked,deadline,completed,requeued,node_fail,failed,preempted,boot_fail",
                "-o",
                "jobid,jobname,partition,account,alloccpus,state,exitcode,end",
                "-S",
                "2021-04-07T23:55:00",
            ],
        ),
    ],
)
def test_cli_patch(
    fake_process: FakeProcess,
    args: List[str],
    expected_args: List[str],
    dataset_contents: str,
) -> None:
    # used to process -S and -E and other dates. we don't actually care about
    # number of occurrences, so just pick a suitably large number
    fake_process.pass_command(["date", fake_process.any()])
    # https://github.com/aklajnert/pytest-subprocess/issues/40
    fake_process.keep_last_process(True)

    pattern = re.compile(r"2021-04-08")

    expected_cmd = ("sacct", *expected_args)
    fake_process.register_subprocess(
        expected_cmd,
        # cast() because https://github.com/aklajnert/pytest-subprocess/issues/41
        stdout=cast(List[Union[str, bytes]], dataset_contents.split("\n")),
    )
    runner = CliRunner(mix_stderr=False, env={"TZ": "America/Los_Angeles"})

    result = runner.invoke(main, args, catch_exceptions=False)

    assert result.exit_code == 0
    assert fake_process.call_count(expected_cmd) == 1
    assert fake_process.call_count(["date", fake_process.any()]) > 0
    assert result.stdout != ""
    assert result.stdout != dataset_contents
    assert all(pattern.search(line) is None for line in result.stdout.split("\n"))


@pytest.mark.parametrize(
    "args, non_sacct_args, expected_stripped",
    [
        (
            ["--arg1", "--arg2", "value", "--arg3=value", "-o"],
            set(),
            ["--arg1", "--arg2", "value", "--arg3=value", "-o"],
        ),
        (
            ["--arg1", "--arg2", "value", "--arg3=value", "-o"],
            {"--arg2"},
            ["--arg1", "--arg3=value", "-o"],
        ),
        (
            ["--arg1", "--arg2", "value", "--arg3=value", "-o"],
            {"--arg3"},
            ["--arg1", "--arg2", "value", "-o"],
        ),
        (
            ["--arg1", "--arg2", "value", "--arg3=value", "-o"],
            {"--arg2", "--arg3"},
            ["--arg1", "-o"],
        ),
    ],
)
def test_strip_non_sacct_args(
    args: List[str], non_sacct_args: Set[str], expected_stripped: List[str]
) -> None:
    assert strip_non_sacct_args(args, non_sacct_args) == expected_stripped
