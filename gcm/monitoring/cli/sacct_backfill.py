#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""A script to backfill sacct data into sink.

Authentication to the Graph API is handled using the GRAPH_API_ACCESS_TOKEN.

This script is by no means idempotent. That is,
if invoked twice on the same underlying `sacct` data, this script will write the data
twice. Downstream data processing should account for this
fact and decide what to do with duplicate data.
"""
import csv
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import timedelta
from ipaddress import ip_address, IPv4Address, IPv6Address
from multiprocessing.managers import BaseManager
from queue import Queue
from types import FrameType
from typing import (
    Callable,
    Generator,
    Iterable,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from uuid import UUID

import click
import clusterscope
from click_option_group import optgroup

from gcm.monitoring.click import (
    cluster_option,
    interval_option,
    log_folder_option,
    log_level_option,
    once_option,
)
from gcm.monitoring.clock import Clock, ClockImpl
from gcm.monitoring.coerce import non_negative_int
from gcm.monitoring.date import BoundedClosedInterval, get_datetime
from gcm.monitoring.slurm.constants import TERMINAL_JOB_STATES
from gcm.monitoring.utils.monitor import init_logger
from typeguard import typechecked

LOGGER_NAME = "sacct_backfill"
logger: logging.Logger = logging.getLogger(
    LOGGER_NAME
)  # default logger to be overridden in main()

IPAddress = Union[IPv4Address, IPv6Address]


# we've observed python leaking the multiprocessing.resource_tracker instance
# when running gcm on containers, this is a known python issue:
# https://github.com/python/cpython/issues/88887
def reap_children(signum: int, frame: Optional[FrameType]) -> None:
    try:
        # -1 meaning wait for any child process, see https://linux.die.net/man/2/waitpid
        # WNOHANG for waitpid to return immediately instead of waiting, if there is no child process ready to be noticed.
        # see https://www.gnu.org/software/libc/manual/html_node/Process-Comption.html#index-WNOHANG
        while os.waitpid(-1, os.WNOHANG)[0] > 0:
            pass
    except ChildProcessError:
        pass


# SIGCHLD is sent to a process to indicate a child process stopped or terminated
# https://man7.org/linux/man-pages/man7/signal.7.html
signal.signal(signal.SIGCHLD, reap_children)


@dataclass
class Obj:
    publish_fn: Callable[[BoundedClosedInterval, Tuple[str, ...], str], None]
    concurrently: int
    sleep: int
    cluster: str
    once: bool
    interval: int
    clock: Clock = field(default_factory=ClockImpl)


@click.group(help=__doc__)
@click.option(
    "--sleep",
    type=non_negative_int,
    default=10,
    help=(
        "Number of seconds to wait before publishing the next chunk. "
        "Does nothing if publishing concurrently."
    ),
)
@click.option(
    "--sacct-timeout",
    type=non_negative_int,
    default=120,
    help="Number of seconds to wait for each `sacct` call to exit.",
)
@click.option(
    "--publish-timeout",
    type=non_negative_int,
    default=120,
    help=(
        "Number of seconds to wait for each `sacct_publish` call to exit. "
        "`sacct_publish` is called each time `sacct` is called."
    ),
)
@click.option(
    "--concurrently",
    type=non_negative_int,
    default=1,
    help=(
        "Maximum number of publishes that can occur concurrently. "
        "Pass 0 to have unlimited concurrency. "
    ),
)
@cluster_option
@once_option
@interval_option(default=3600)
@optgroup.group("Rendezvous options. Options for synchronizing backfill processes.")
@optgroup.option(
    "--rendezvous-host",
    type=ip_address,
    help=(
        "The host running a rendezvous server for synchronizing backfills "
        "across multiple clusters."
    ),
)
@optgroup.option(
    "--rendezvous-port",
    type=non_negative_int,
    default=50000,
    help="The port the rendezvous server is listening on.",
)
@optgroup.option(
    "--authkey",
    help=("A UUID hex string used to authenticate to the rendezvous server. "),
)
@optgroup.option(
    "--rendezvous-timeout",
    type=non_negative_int,
    default=60,
    help="Number of seconds to wait for other processes to synchronize.",
)
@click.option(
    "--stdout",
    is_flag=True,
    default=False,
    help="Whether to log information to stdout.",
)
@log_folder_option
@log_level_option
@click.pass_context
@typechecked
def main(
    ctx: click.Context,
    sleep: int,
    sacct_timeout: int,
    publish_timeout: int,
    concurrently: int,
    cluster: Optional[str],
    once: bool,
    interval: int,
    rendezvous_host: Optional[IPAddress],
    rendezvous_port: Optional[int],
    authkey: Optional[str],
    rendezvous_timeout: int,
    stdout: bool,
    log_folder: str,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
) -> None:
    check_python_version()

    if cluster is None:
        cluster = clusterscope.cluster()

    global logger
    # The default global logger use a stream handler to stdout
    logger, _ = init_logger(
        logger_name=LOGGER_NAME,
        log_dir=os.path.join(log_folder, LOGGER_NAME + "_logs"),
        log_name=cluster + ".log",
        log_stdout=stdout,
        log_level=getattr(logging, log_level),
    )

    manager = get_manager(rendezvous_host, rendezvous_port, authkey)

    def _publish_chunk(
        interval: BoundedClosedInterval, publish_cmd: Tuple[str, ...], cluster: str
    ) -> None:
        def thunk() -> None:
            publish_chunk(
                publish_cmd,
                interval,
                cluster,
                sacct_timeout_sec=sacct_timeout,
                publish_timeout_sec=publish_timeout,
            )

        if manager is None:
            thunk()
            return

        start_iso = interval.lower.isoformat(sep="T")
        end_iso = interval.upper.isoformat(sep="T")
        b = manager.get_barrier(start_iso, end_iso)  # type: ignore[attr-defined]
        logger.info(
            f"Waiting on other processes for chunk {start_iso} {end_iso} to start."
        )
        b.wait(timeout=rendezvous_timeout)
        logger.info("Starting")
        try:
            thunk()
        finally:
            timeout = sacct_timeout + publish_timeout + rendezvous_timeout
            logger.info(
                f"Waiting for other processes to finish chunk {start_iso} {end_iso} for {timeout:n} seconds."
            )
            b.wait(timeout=timeout)

    if ctx.obj is None:
        ctx.obj = Obj(
            publish_fn=_publish_chunk,
            concurrently=concurrently,
            sleep=sleep,
            cluster=cluster,
            once=once,
            interval=interval,
        )


def publish_all_serial(
    chunk_iter: Iterable[BoundedClosedInterval],
    publish_one: Callable[[BoundedClosedInterval, Tuple[str, ...], str], None],
    publish_cmd: Tuple[str, ...],
    cluster: str,
    *,
    sleep: int,
) -> None:
    it = iter(chunk_iter)
    ival = next(it)
    publish_one(ival, publish_cmd, cluster)
    for ival in it:
        time.sleep(sleep)
        publish_one(ival, publish_cmd, cluster)


def publish_all_parallel(
    chunk_iter: Iterable[BoundedClosedInterval],
    publish_one: Callable[[BoundedClosedInterval, Tuple[str, ...], str], None],
    publish_cmd: Tuple[str, ...],
    cluster: str,
    *,
    max_concurrency: Optional[int] = None,
) -> None:
    global logger
    sem = threading.Semaphore(max_concurrency) if max_concurrency is not None else None
    work_queue: "Queue[Optional[BoundedClosedInterval]]" = Queue()

    def consumer(e: ThreadPoolExecutor) -> None:
        def release_semaphore() -> None:
            if sem is not None:
                sem.release()

        fs = []
        try:
            while True:
                work = work_queue.get()
                if work is None:
                    return

                logger.debug(f"Consumer processing {work}")
                f = e.submit(publish_one, work, publish_cmd, cluster)
                f.add_done_callback(lambda _: release_semaphore())
                fs.append(f)
        finally:
            logger.debug("Consumer exiting")
            wait(fs)

    def producer() -> None:
        for chunk in chunk_iter:
            if sem is not None:
                sem.acquire()
            logger.debug(f"Producer queueing {chunk}")
            work_queue.put(chunk)
        logger.debug("Producer exiting")
        work_queue.put(None)

    with ThreadPoolExecutor() as e:
        consume_fut = e.submit(consumer, e)
        produce_fut = e.submit(producer)
        wait([consume_fut, produce_fut])


def check_python_version() -> None:
    if sys.version_info >= (3, 7):
        return

    version_str = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    print(f"This script requires Python >= 3.7, but got {version_str}", file=sys.stderr)
    sys.exit(1)


def first_line(s: str) -> str:
    return s.split("\n")[0]


@main.command("new")
@click.option(
    "-s",
    "--start",
    default="3 hours ago",
    help="Start time (inclusive) in a format understood by `date -d`.",
)
@click.option(
    "-e",
    "--end",
    default="now",
    help="End time (inclusive) in a format understood by `date -d`.",
)
@click.option(
    "--step",
    type=non_negative_int,
    default=1,
    help="Size of the time window per call to `sacct` in hours.",
)
@click.argument("publish_cmd", nargs=-1)
@click.pass_obj
@typechecked
def new(
    obj: Obj,
    start: str,
    end: str,
    step: int,
    publish_cmd: Tuple[str, ...],
) -> None:
    """Start a new backfill.

    The range of the backfill is specified by the `-s` and `-e` options. In order to
    reduce the load on the SLURM database, this range is partitioned into chunks and
    we invoke `sacct` on each chunk, one at a time. The size of each chunk is controlled
    by the `--step` option.

    Since we may be backfilling over a large range, there may be chunks which fail.
    Chunks which fail log an error to STDERR. To retry failed chunks, redirect
    STDERR to a file, then use the `from_file` subcommand after the current invocation
    finishes.

    Examples:
        # dry run; prints JSON to stdout. see P167830725 for example output
        gcm sacct_backfill \\
            --once \\
            new \\
            -s 'today 4pm' \\
            -e 'today 5pm' \\
            -- \\
            gcm sacct_publish -n

        # write to test category; run `ptail -f fair_cluster_sacct_test` on a devserver
        # to verify incoming data
        gcm sacct_backfill --once new -s 'today 4pm' -e 'today 5pm' \\
            -- \\
            gcm sacct_publish \\
            --sink graph_api \\
            -o app_secret=$APP_SECRET \\
            -o scribe_category=fair_cluster_sacct_test

        # write to actual category
        gcm sacct_backfill --once new -s 'today 4pm' -e 'today 5pm' \\
            -- \\
            gcm sacct_publish \\
            --sink graph_api \\
            -o app_secret=$APP_SECRET \\
            -o scribe_category=fair_cluster_sacct

        # write to actual category, recording errors in a file and retrying later
        gcm sacct_backfill --once new -s 'jan 1 2020 12am' -e 'dec 31 2020 11:59:59pm' \\
            -- \\
            gcm sacct_publish \\
            --sink graph_api \\
            -o app_secret=$APP_SECRET \\
            -o scribe_category=fair_cluster_sacct 2> errors-1.log
        ./my_error_postprocessing errors-1.log | gcm sacct_backfill --once from_file \\
            -- \\
            gcm sacct_publish \\
            --sink graph_api \\
            -o app_secret=$APP_SECRET \\
            -o scribe_category=fair_cluster_sacct 2> errors-2.log
        # repeat until there are no errors

    """
    while True:
        run_st_time = obj.clock.monotonic()

        it = gen_time_bounds(
            BoundedClosedInterval(
                lower=get_datetime(start),
                upper=get_datetime(end),
            ),
            timedelta(hours=step),
        )

        if obj.concurrently == 1:
            publish_all_serial(
                it,
                obj.publish_fn,
                publish_cmd=publish_cmd,
                sleep=obj.sleep,
                cluster=obj.cluster,
            )
        else:
            publish_all_parallel(
                it,
                obj.publish_fn,
                publish_cmd=publish_cmd,
                max_concurrency=obj.concurrently if obj.concurrently > 0 else None,
                cluster=obj.cluster,
            )

        if obj.once:
            break

        time_running_last_collection = obj.clock.monotonic() - run_st_time
        obj.clock.sleep(max(0, obj.interval - time_running_last_collection))


@main.command("from_file")
@click.option("--intervals", type=click.File("r"), default=sys.stdin)
@click.argument("publish_cmd", nargs=-1)
@click.pass_obj
@typechecked
def from_file(
    obj: Obj,
    intervals: str,
    publish_cmd: Tuple[str, ...],
) -> None:
    """Backfill from a comma separated file of (start, end) intervals.

    Each element of the pair is a string understood by `date -d`.

    Examples:
        # creating intervals.csv
        echo "yesterday 8:35am,yesterday 8:35:01am\ntoday 8:35am,today 8:35:01am" > intervals.csv

        # dry run from a file; prints JSON to stdout
        gcm sacct_backfill \\
            --once \\
            --extra-flags='-n' \\
            from_file \\
            --intervals intervals.csv \\
            -- \\
            gcm sacct_publish -n

        # dry run from STDIN
        cat intervals.csv | gcm sacct_backfill \\
            --once \\
            from_file \\
            -- \\
            gcm sacct_publish -n

        # write to test category; run `ptail -f fair_cluster_sacct_test` on a devserver
        # to verify incoming data
        gcm sacct_backfill from_file --intervals intervals.csv \\
            --once \\
            -- \\
            gcm sacct_publish \\
            --sink graph_api \\
            -o app_secret=$APP_SECRET \\
            -o scribe_category=fair_cluster_sacct_test

        # write to actual category
        gcm sacct_backfill from_file --intervals intervals.csv \\
            --once \\
            -- \\
            gcm sacct_publish \\
            --sink graph_api \\
            -o app_secret=$APP_SECRET \\
            -o scribe_category=fair_cluster_sacct
    """

    def gen_intervals() -> Generator[BoundedClosedInterval, None, None]:
        reader = csv.reader(intervals)
        for row in reader:
            start, end = [get_datetime(d) for d in row]
            yield BoundedClosedInterval(lower=start, upper=end)

    it = gen_intervals()
    if obj.concurrently == 1:
        publish_all_serial(
            it,
            obj.publish_fn,
            publish_cmd=publish_cmd,
            sleep=obj.sleep,
            cluster=obj.cluster,
        )
    else:
        publish_all_parallel(
            it,
            obj.publish_fn,
            publish_cmd=publish_cmd,
            max_concurrency=obj.concurrently if obj.concurrently > 0 else None,
            cluster=obj.cluster,
        )


def host_port(s: str) -> Tuple[IPAddress, int]:
    raw_host, raw_port = s.split(":")
    return (ip_address(raw_host), int(raw_port))


def gen_time_bounds(
    interval: BoundedClosedInterval, step: timedelta
) -> Generator[BoundedClosedInterval, None, None]:
    """A generator which splits the time interval [start, end] into step-size chunks
    assuming at most 1-second granularity.

    That is,
        [start, start + step - 1s],
        [start + step, start + 2 * step - 1s],
        ...,
        [start + n * step, end]

    Parameters:
        interval: The interval to partition
        step: The size of each subinterval. Must be greater than one second.
    """
    if step <= timedelta(seconds=1):
        raise ValueError(f"Step must be greater than one second but got {step}")

    start = interval.lower
    end = interval.upper
    while start + step < end:
        yield BoundedClosedInterval(
            lower=start, upper=start + step - timedelta(seconds=1)
        )
        start += step
    yield BoundedClosedInterval(lower=start, upper=end)


def publish_chunk(
    publish_cmd: Sequence[str],
    interval: BoundedClosedInterval,
    cluster: str,
    *,
    sacct_timeout_sec: int = 120,
    publish_timeout_sec: int = 120,
) -> None:
    """Publish sacct data about jobs which entered a terminal state in the interval
    [start, end].

    Parameters:
        publish_cmd: A command which takes `sacct` output in stdin and writes it to a
            sink.
        interval: Only include jobs which entered a terminal state during this time.
        sacct_timeout_sec: The duration in seconds to wait for `sacct` to exit
        publish_timeout_sec: The duration in seconds to wait for `sacct_publish` to exit
    """
    start_iso = interval.lower.isoformat(sep="T")
    end_iso = interval.upper.isoformat(sep="T")
    global logger
    logger.info(f"Chunk {start_iso} {end_iso}")

    with subprocess.Popen(
        [
            "gcm",
            "fsacct",
            "--wrapper-batch-size",
            "1000",
            "-P",
            "-S",
            start_iso,
            "-E",
            end_iso,
            "-s",
            ",".join(TERMINAL_JOB_STATES),
            "-a",
            "-o",
            "all",
            "--duplicates",
            "--noconvert",
            "--clusters",
            cluster,
        ],
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ) as sacct_proc:
        assert sacct_proc.stdout is not None, "stdout should be piped"
        with subprocess.Popen(
            publish_cmd,
            stdin=sacct_proc.stdout,
        ) as publish_proc:
            try:
                sacct_proc.wait(timeout=sacct_timeout_sec)
            except subprocess.TimeoutExpired:
                logger.exception(f"Failed to publish {start_iso} {end_iso}")
                publish_proc.terminate()
                sacct_proc.terminate()
                return
            sacct_proc.stdout.close()

            if sacct_proc.returncode != 0:
                logger.error(f"Failed to publish {start_iso} {end_iso}")
                logger.error(f"`sacct` exited with exit code {sacct_proc.returncode}")
                return

            try:
                publish_proc.wait(timeout=publish_timeout_sec)
            except subprocess.TimeoutExpired:
                publish_proc.terminate()
                logger.exception(f"Failed to publish {start_iso} {end_iso}")
                return

            if publish_proc.returncode != 0:
                logger.error(f"Failed to publish {start_iso} {end_iso}")
                logger.error(
                    f"`sacct_publish` exited with exit code {publish_proc.returncode}"
                )
                return


class Manager(BaseManager):
    pass


Manager.register("get_barrier")


def get_manager(
    host: Optional[IPAddress], port: Optional[int], authkey: Optional[str]
) -> Optional[Manager]:
    global logger
    if host is None:
        logger.info("Host is None, not returning Manager")
        return None

    if port is None:
        raise ValueError("'port' must not be none if 'host' is not None")

    if authkey is None:
        raise ValueError("'authkey' must not be None if 'host' is not None")

    logger.info(f"Connecting to manager at {host}:{port}")
    m = Manager(address=(str(host), port), authkey=UUID(hex=authkey).bytes)
    m.connect()
    return m
