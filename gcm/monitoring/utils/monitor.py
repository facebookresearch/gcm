#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Utility functions for the various monitors."""
from __future__ import annotations

import inspect
import logging
import logging.handlers
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import (
    Callable,
    Collection,
    Iterable,
    Literal,
    Mapping,
    Optional,
    Tuple,
    TYPE_CHECKING,
)

import click
from gcm.monitoring.clock import Clock
from gcm.monitoring.sink.protocol import SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import (
    Factory,
    get_message_for_sink_init_error,
    write_to_sink_with_retries,
)
from gcm.monitoring.utils.error import log_error
from omegaconf import OmegaConf as oc
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


def init_logger(
    logger_name: str,
    log_dir: str,
    log_name: str,
    log_formatter: Optional[logging.Formatter] = logging.Formatter(
        "[%(asctime)s] - [%(levelname)s] - [%(name)s] - %(message)s"
    ),
    log_level: int = logging.INFO,
    max_bytes: int = 1024 * 1024,
    backup_count: int = 2,
    log_stdout: bool = False,
) -> Tuple[logging.Logger, logging.Handler]:
    """Set up logging for a cluster monitor.

    Logs are stored at: {log_dir}/{log_name}
    """
    file_path = os.path.join(log_dir, log_name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    handler: logging.Handler = logging.Handler()

    if log_stdout:
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = RotatingFileHandler(
            file_path, mode="a", maxBytes=max_bytes, backupCount=backup_count
        )

    if log_formatter:
        handler.setFormatter(log_formatter)
    logger.addHandler(handler)

    return logger, handler


def run_data_collection_loop(
    logger_name: str,
    log_folder: str,
    stdout: bool,
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    cluster: str,
    clock: Clock,
    once: bool,
    interval: int,
    data_collection_tasks: list[
        tuple[
            Callable[[str, int, logging.Logger], Iterable[DataclassInstance]],
            SinkAdditionalParams,
        ]
    ],
    sink: str,
    sink_opts: Collection[str],
    chunk_size: int,
    retries: int,
    dry_run: bool,
    registry: Mapping[str, Factory[SinkImpl]],
) -> None:
    logger, _ = init_logger(
        logger_name=logger_name,
        log_dir=os.path.join(log_folder, logger_name + "_logs"),
        log_name=logger_name + ".log",
        log_stdout=stdout,
        log_level=getattr(logging, log_level),
    )
    if dry_run:
        logger.debug("this is a `--dry-run`, will print data to stdout")
        sink = "stdout"
    try:
        sink_factory = typechecked(registry[sink])
    except KeyError:
        raise click.UsageError(
            f"Sink '{sink}' could not be found. Here are the sinks that are registered:\n\t{list(registry.keys())}"
        )
    sink_kwargs = oc.from_dotlist(list(sink_opts))
    try:
        sink_impl = sink_factory(**sink_kwargs)
    except TypeError as e:
        msg = get_message_for_sink_init_error(e, sink, sink_factory, sink_kwargs)
        if msg is None:
            raise
        raise click.UsageError(str(msg)) from e

    if not isinstance(sink_impl, expected_proto := SinkImpl):
        sink_module = inspect.getmodule(sink_impl)
        proto_module = inspect.getmodule(expected_proto)
        raise click.ClickException(
            f"Sink '{sink}' defined in\n"
            f"\t{sink_module.__name__}\n"
            f"does not appear to implement {expected_proto.__name__} defined in\n"
            f"\t{proto_module.__name__}"
        )

    logger.debug("will log data to %s", sink)
    _write = log_error(logger_name)(sink_impl.write)

    while True:
        logger.debug("starting new data collection for %s", logger_name)
        run_st_time = clock.monotonic()
        log_time = clock.unixtime()

        for get_data, additional_params in data_collection_tasks:
            logger.debug("will try getting data for %s", logger_name)
            data = get_data(
                cluster,
                interval,
                logger,
            )
            logger.debug("succeeded getting data for %s", logger_name)
            if data is not None:
                logger.debug("will write %s data to sink %s", logger_name, sink)
                write_to_sink_with_retries(
                    write=_write,
                    sink=sink,
                    records=data,
                    chunk_size=chunk_size,
                    retries=retries,
                    verbose=(getattr(logging, log_level) == logging.DEBUG),
                    log_time=log_time,
                    additional_params=additional_params,
                )
                logger.debug("succeeded writing %s data to sink %s", logger_name, sink)

        if once:
            logger.debug("stopping data collection due to `--once`")
            break

        time_running_last_collection = clock.monotonic() - run_st_time
        sleep_time = max(0, interval - time_running_last_collection)
        logger.debug(
            "last data collection took %d seconds", time_running_last_collection
        )
        logger.debug(
            "will sleep %d seconds before starting next collection", sleep_time
        )
        clock.sleep(sleep_time)
