# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import itertools
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import takewhile, zip_longest
from typing import (
    Callable,
    cast,
    Collection,
    Container,
    Generator,
    IO,
    Iterable,
    List,
    NewType,
    Optional,
    Tuple,
    TypeVar,
)

import click
from gcm.monitoring import timezone
from gcm.monitoring.clock import time_to_time_aware
from gcm.monitoring.date import ClosedInterval, get_datetime, get_datetimes

from gcm.monitoring.slurm.constants import (
    SACCT_DATE_FIELDS,
    SLURM_CLI_DELIMITER,
    TERMINAL_JOB_STATES,
)
from typeguard import typechecked

logger = logging.getLogger(__name__)


# args which are specific to this wrapper and should never be forwarded to `sacct`
# NOTE: args here are expected to have a value (i.e. they aren't flags)
NON_SACCT_ARGS = frozenset(["--wrapper-batch-size"])

TimeAwareSacct = NewType("TimeAwareSacct", List[str])


class UnixDate(click.ParamType):
    name = "date"

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> datetime:
        logger.debug(f"Trying to convert: {value}")
        try:
            return get_datetime(value)
        except ValueError as e:
            logger.debug(e, exc_info=True)
            self.fail(f"`date -d` could not parse value: {value}", param, ctx)
        except TypeError:
            self.fail(f"Expected str but got {type(value).__name__}", param, ctx)


class CommaList(click.ParamType):
    name = "list"

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> List[str]:
        if value == "":
            self.fail("List should be non-empty", param, ctx)
        return value.split(",")


T = TypeVar("T")


def last_value(
    ctx: click.Context, param: click.Parameter, value: List[T]
) -> Optional[T]:
    try:
        return value[-1]
    except IndexError:
        return None


def flatten(
    ctx: click.Context, param: click.Parameter, value: List[List[T]]
) -> List[T]:
    return list(itertools.chain(*value))


@typechecked
@dataclass
class ContextObject:
    argv: Tuple[str, ...]


@click.command(
    context_settings={
        "ignore_unknown_options": True,
        "help_option_names": [],
    }
)
@click.argument("all_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def main(ctx: click.Context, all_args: Tuple[str, ...]) -> None:
    # We want access to the full unparsed argument list in main_impl. Click doesn't
    # provide a direct API to get them (sys.argv is NOT always what's passed to our
    # command, e.g. in unit tests). To handle this, we just wrap our impl in a dummy
    # command which captures the full unprocessed argument list and store it in the
    # context
    ctx.obj = ContextObject(argv=all_args)
    sub_ctx = main_impl.make_context("main_impl", list(all_args), parent=ctx)
    sub_ctx.forward(main_impl)


@click.command(
    context_settings={
        "ignore_unknown_options": True,
        "help_option_names": ["--wrapper-help"],
    },
)
@click.option(
    "--starttime",
    "-S",
    type=UnixDate(),
    multiple=True,
    callback=last_value,
    help="Start time in a format parsable by `date -d`.",
)
@click.option(
    "--endtime",
    "-E",
    type=UnixDate(),
    multiple=True,
    callback=last_value,
    help="End time in a format parsable by `date -d`.",
)
@click.option(
    "-o",
    "--format",
    "fmt_list",
    type=CommaList(),
    multiple=True,
    callback=flatten,
    default=[
        os.getenv(
            "SACCT_FORMAT", "jobid,jobname,partition,account,alloccpus,state,exitcode"
        )
    ],
    show_default=True,
    help="List of fields to collect as a comma-separated string",
)
@click.option(
    "-s",
    "--state",
    type=CommaList(),
    multiple=True,
    callback=flatten,
    help="Selects jobs based on their state during the time period given as a comma-separated string.",
)
@click.option(
    "--delimiter",
    default=[
        SLURM_CLI_DELIMITER
    ],  # the delimiter can be any string thats not present in sacct user generated fields
    show_default=True,
    multiple=True,
    callback=last_value,
    help="ASCII character used to delimit fields when using -p or -P",
)
@click.option(
    "--wrapper-batch-size",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="The number of sacct lines the wrapper should process at once.",
)
@click.argument("sacct_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
@typechecked
def main_impl(
    obj: ContextObject,
    starttime: Optional[datetime],
    endtime: Optional[datetime],
    fmt_list: List[str],
    state: List[str],
    delimiter: str,
    wrapper_batch_size: int,
    sacct_args: Tuple[str, ...],
) -> None:
    """A wrapper around `sacct` which strictly respects time bounds when using
    `--parsable2` and only jobs in terminal states are requested.

    Occasionally, when using `sacct -S $start -E $end -s $states`, you will get jobs
    with `End` time just outside of the given [$start, $end] interval (typically 2-3
    minutes before $start or 2-3 minutes after $end`). This wrapper filters out these
    jobs at the boundary so that for all jobs returned, `End` is strictly in
    [$start, $end].
    """
    if not should_patch_sacct_cmd(sacct_args, starttime, endtime, state):
        logger.debug("Not modifying any sacct args")
        sys.exit(
            subprocess.run(
                [
                    "sacct",
                    *strip_non_sacct_args(obj.argv, NON_SACCT_ARGS),
                ]
            ).returncode
        )

    def other_extensions(args: List[str]) -> None:
        if endtime is not None:
            # XXX: _as_naive_local_time because sacct does not understand UTC offsets
            args.extend(["-E", _to_naive_local_time(endtime).isoformat(sep="T")])
        args.extend(["--delimiter", delimiter])
        if len(state) > 0:
            args.extend(["--state", ",".join(state)])

    patched_cmd = get_patched_sacct_cmd(
        sacct_args, starttime, fmt_list, other_extensions=other_extensions
    )
    logger.debug(f"patched command: {patched_cmd}")
    with subprocess.Popen(
        patched_cmd, stdout=subprocess.PIPE, text=True, errors="replace"
    ) as p:
        stdout = p.stdout
        assert stdout is not None, "It should be piped due to subprocess.PIPE"

        get_stdout = get_sacct_lines(stdout, delimiter)
        for line in filter_sacct_lines(
            get_stdout,
            filter_impl=lambda sacct_io, line_splitter, line_formatter, line_last_column_splitter: filter_sacct_lines_batched(
                sacct_io,
                line_splitter,
                line_formatter,
                line_last_column_splitter,
                ClosedInterval(starttime, endtime),
                batch_size=wrapper_batch_size,
            ),
            delimiter=delimiter,
            has_header="-n" not in sacct_args and "--noheader" not in sacct_args,
        ):
            print(line)

    sys.exit(p.returncode)


def _to_naive_local_time(t: datetime) -> datetime:
    """Convert a time to an unlocalized time."""
    tz = timezone.get_local()
    logger.debug(f"local timezone: {tz}")
    return t.astimezone(tz).replace(tzinfo=None)


def should_patch_sacct_cmd(
    sacct_args: Container[str],
    starttime: Optional[datetime],
    endtime: Optional[datetime],
    states: Collection[str],
) -> bool:
    return (
        (starttime is not None or endtime is not None)
        # empty states means all states, not all job states are terminal
        and len(states) > 0
        and set(s.lower() for s in states) <= TERMINAL_JOB_STATES
        and ("-h" not in sacct_args and "--help" not in sacct_args)
        and ("-P" in sacct_args or "--parsable2" in sacct_args)
    )


def strip_non_sacct_args(
    args: Collection[str], non_sacct_args: Collection[str]
) -> List[str]:
    non_sacct_arg_patterns = [re.escape(f"{arg}=") for arg in non_sacct_args]
    # match args of the form "--arg=value"
    args_with_value_pattern = (
        re.compile(
            r"^({patterns}).*$".format(patterns="|".join(non_sacct_arg_patterns))
        )
        if len(non_sacct_arg_patterns) > 0
        else None
    )

    stripped_args = []
    args_iter = iter(args)
    while True:
        try:
            arg = next(args_iter)
        except StopIteration:
            break

        if arg in non_sacct_args:
            # next arg is the value, skip it
            next(args_iter)
            continue

        if args_with_value_pattern is not None and args_with_value_pattern.fullmatch(
            arg
        ):
            continue

        stripped_args.append(arg)
    return stripped_args


def get_sacct_lines(stdout: IO[str], delimiter: str) -> Generator[str, None, None]:
    """
    Gets a sacct stdout (does post processing to clean
    user generated fields) and generates a single sacct line
    at a time.

    post processing steps:
    - \n (line breaker) removal: \n in user generated fields cause
        issues when parsing.

    """
    first_line = stdout.readline()
    yield first_line
    fields_number = first_line.count(delimiter)

    prev_line, prev_line_delimiters = "", 0
    for line in stdout:
        line_delimiters = line.count(delimiter)
        if line_delimiters < fields_number:
            if prev_line_delimiters + line_delimiters == fields_number:
                yield prev_line + line
                prev_line = ""
                prev_line_delimiters = 0
                continue
            elif prev_line_delimiters + line_delimiters > fields_number:
                raise Exception(
                    f"The following sacct line has more delimiters than expected: {line}"
                )

            # escape line breakers
            prev_line += line.replace("\n", "\\n")
            prev_line_delimiters += line_delimiters
        else:
            yield line


def get_patched_sacct_cmd(
    sacct_args: Iterable[str],
    starttime: Optional[datetime],
    fmt_list: List[str],
    *,
    start_time_slack: timedelta = timedelta(minutes=2),
    other_extensions: Optional[Callable[[List[str]], None]] = None,
) -> List[str]:
    if len(fmt_list) == 0:
        raise ValueError("Cannot have empty format list")

    if start_time_slack < timedelta(0):
        raise ValueError(f"Slack cannot be negative, but got {start_time_slack}")

    sacct_arg_lst = list(sacct_args)
    logger.debug(f"Original sacct args: {sacct_arg_lst}")
    if other_extensions is not None:
        other_extensions(sacct_arg_lst)
    sacct_arg_lst.extend(["-o", ",".join(fmt_list + ["end"])])
    if starttime is not None:
        sacct_arg_lst.extend(
            [
                "-S",
                # NOTE: sacct reports some jobs as ending after the given
                # bound, so we relax the lower bound in order to fetch those
                # jobs. E.g. suppose we request the following two intervals:
                #   [t, t + 1), [t + 1, t + 2).
                # Then sacct may return jobs in the first interval with end
                # time > t + 1, so we will filter them out. In order to make
                # sure we capture them, we need to start the next interval at t + 1 - ε
                # for some ε > 0.
                # XXX: _as_naive_local_time because sacct does not understand UTC offsets
                _to_naive_local_time(starttime - start_time_slack).isoformat(sep="T"),
            ]
        )
    return ["sacct", *sacct_arg_lst]


TLineSplitterCallable = Callable[[str], List[str]]
TLineFormatterCallable = Callable[[List[str]], TimeAwareSacct]
TLineLastColumnSplitterCallable = Callable[[List[str]], Tuple[str, str]]


def filter_sacct_lines_one_by_one(
    sacct_io: Generator[str, None, None],
    line_splitter: TLineSplitterCallable,
    line_formatter: TLineFormatterCallable,
    line_last_column_splitter: TLineLastColumnSplitterCallable,
    interval: ClosedInterval,
) -> Generator[str, None, None]:
    for line in sacct_io:
        stripped = line.strip()
        if stripped == "":
            continue

        split_line = line_splitter(stripped)
        formatted_line = line_formatter(split_line)
        actual_line, end = line_last_column_splitter(formatted_line)
        if get_datetime(end) in interval:
            yield actual_line
        else:
            logger.debug(f"Filtered: {actual_line}")


TFilterCallable = Callable[
    [
        Generator[str, None, None],
        TLineSplitterCallable,
        TLineFormatterCallable,
        TLineLastColumnSplitterCallable,
    ],
    Iterable[str],
]


def filter_sacct_lines(
    sacct_io: Generator[str, None, None],
    *,
    filter_impl: TFilterCallable,
    delimiter: str,
    has_header: bool,
) -> Generator[str, None, None]:
    def split_line(line: str) -> List[str]:
        return line.split(delimiter)

    def split_last_column(line: List[str]) -> Tuple[str, str]:
        *cols, last = line
        return delimiter.join(cols), last

    date_fields_indices = []
    if has_header:
        header = next(sacct_io).strip()
        split_header = split_line(header)
        date_fields_indices = [
            i for i, field in enumerate(split_header) if field in SACCT_DATE_FIELDS
        ]
        yield split_last_column(split_header)[0]

    def format_line(line: List[str]) -> TimeAwareSacct:
        # reconstruct date fields to follow PST timezone in ISO8601 format
        for date_field_index in date_fields_indices:
            line[date_field_index] = time_to_time_aware(line[date_field_index])

        return TimeAwareSacct(line)

    yield from filter_impl(sacct_io, split_line, format_line, split_last_column)


def filter_sacct_lines_batched(
    sacct_io: Generator[str, None, None],
    line_splitter: TLineSplitterCallable,
    line_formatter: TLineFormatterCallable,
    line_last_column_splitter: TLineLastColumnSplitterCallable,
    interval: ClosedInterval,
    *,
    batch_size: int = 1000,
) -> Generator[str, None, None]:
    if batch_size < 1:
        raise ValueError("Batch size must be positive")

    if batch_size == 1:
        logger.debug("Got batch size 1; not batching.")
        yield from filter_sacct_lines_one_by_one(
            sacct_io, line_splitter, line_formatter, line_last_column_splitter, interval
        )
        return

    def split_lines(
        lines: Generator[str, None, None],
    ) -> Generator[Tuple[str, str], None, None]:
        for line in lines:
            stripped = line.strip()
            if stripped == "":
                continue

            split_line = line_splitter(stripped)
            formatted_line = line_formatter(split_line)
            yield line_last_column_splitter(formatted_line)

    Ta = TypeVar("Ta")

    def batch_iter(
        it: Iterable[Ta], batch_size: int
    ) -> Generator[Tuple[Ta, ...], None, None]:
        """Batch an iterable into batches at most batch_size."""

        class FillValue:
            """Dummy fill value to handle extra elements"""

        fill_value = FillValue()
        iters = [iter(it)] * batch_size
        for batch in zip_longest(*iters, fillvalue=fill_value):
            yield tuple(
                # SAFETY: `batch` is constructed from `iters` which only have elements
                # of type `Ta`, therefore `batch` must also only have elements of `Ta`
                takewhile(lambda x: x != fill_value, cast(Tuple[Ta, ...], batch))
            )

    for batch in batch_iter(split_lines(sacct_io), batch_size):
        actual_lines, ends = zip(*batch)
        for actual_line, end in zip(actual_lines, get_datetimes(ends)):
            if end in interval:
                yield actual_line
            else:
                logger.debug(f"Filtered: {actual_line}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
    main()
