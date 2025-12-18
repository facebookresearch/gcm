#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Write datapoints to Scribe via GraphQL."""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional
from urllib.parse import urljoin

import requests

from gcm.monitoring.clock import Clock, ClockImpl
from gcm.monitoring.itertools import (
    chunk_by_json_size,
    json_dumps_dataclass,
    json_dumps_dataclass_list,
)
from gcm.monitoring.meta_utils.scuba import ScubaMessage
from requests.exceptions import RequestException

GRAPH_API = "https://graph.facebook.com"
GRAPH_API_VERSION = "v21.0"
BYTES_IN_MB = 1_000_000

logger = logging.getLogger(__name__)


@dataclass
class ScribeConfig:
    secret_key: str
    api: str = GRAPH_API
    graph_api_version: str = GRAPH_API_VERSION
    path: str = "/scribe_logs"
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        try:
            with open(self.secret_key) as f:
                self.secret_key = f.readline().strip()
        except (FileNotFoundError, PermissionError):
            # XXX don't add stack or exception info so that we don't accidentally leak
            # secrets
            logger.info(
                "secret_key does not seem to be a readable file; assuming it is the secret value."
            )

    @property
    def endpoint(self) -> str:
        return urljoin(self.api, self.graph_api_version + self.path)


class ScribeError(Exception):
    pass


class ScribeErrorWithAcks(ScribeError):
    def __init__(self, *args: Any, acks: Optional[List[bool]] = None):
        super().__init__(*args)
        self.acks = acks or []


@dataclass
class ScribeLog:
    category: str
    message: str
    line_escape: bool


def try_write_logs(
    config: ScribeConfig,
    logs: List[ScribeLog],
    timeout: int,
) -> None:
    """Write Scribe logs

    Parameters:
        config: A Scribe config
        logs: A list of logs to write to Scribe
        timeout: Number of seconds to wait for a response from Scribe

    Raises:
        ScribeError: An error occured when writing to Scribe.
        RequestException: An exception occurred when writing to the Scribe endpoint.
        ScribeErrorWithAcks: When using acknowledged writes, not all logs were
            acknowledged.
    """
    payload = {
        "access_token": config.secret_key,
        "logs": json_dumps_dataclass_list(logs),
    }
    response = config.session.post(config.endpoint, json=payload, timeout=timeout)
    response.raise_for_status()
    try:
        response_json = response.json()
    except ValueError as e:
        raise ScribeError(
            f"Error decoding response from Scribe: {response.text}"
        ) from e
    response_codes = response_json["response_codes"]
    acks = [True if response_codes[code] == "OK" else False for code in response_codes]

    if len(acks) != len(logs):
        # If we didn't get enough acks back, we can't be sure they line up
        # coherently with our samples, so just throw.
        raise ScribeError(f"Only got {len(acks)} acks for {len(logs)} messages")

    num_failed = sum(not ack for ack in acks)
    if num_failed == 0:
        return
    raise ScribeErrorWithAcks(
        f"Failed to write {num_failed}/{len(logs)} messages", acks=acks
    )


def write_logs_with_retries(
    logs: List[ScribeLog],
    *,
    config: ScribeConfig,
    timeout: int = 60,
    retries: int = 2,
    backoff: int = 10,
    clock: Clock = ClockImpl(),
) -> None:
    """Write logs with an exponentially increasing timeout and backoff for each try.

    Parameters:
        config: A Scribe config
        logs: The Scribe logs to write
        timeout: The initial number of seconds to wait for a response from the server
            before failing.
        retries: The number of times to retry writes after failure.
        backoff: The initial number of seconds to wait before retrying.
    """
    if retries < 0:
        raise ValueError(f"Cannot retry {retries} < 0 times")

    try_ = 0
    while True:
        try:
            try_write_logs(config, logs, timeout * 2**try_)
        except (ScribeErrorWithAcks, ScribeError, RequestException) as e:
            if try_ >= retries:
                raise ScribeError(f"Used all ({retries}/{retries}) retries") from e

            if isinstance(e, ScribeErrorWithAcks):
                # Retry with only failed logs
                logs = [log for acked, log in zip(e.acks, logs) if not acked]

            clock.sleep(backoff * 2**try_)
            try_ += 1
            continue
        else:
            break


def write_logs(
    write_fn: Callable[[List[ScribeLog]], None],
    logs: Iterable[ScribeLog],
    *,
    chunk_size_bytes: int = 100 * BYTES_IN_MB,
) -> None:
    """Write a sequence of Scribe logs with timeouts, chunking, and retries.

    Raises:
        ValueError: If any log is too large to satisfy the given size hint
        ScribeError: An error occurred when writing logs to Scribe.
    """
    for log_chunk in chunk_by_json_size(logs, chunk_size_bytes, json_dumps_dataclass):
        write_fn(log_chunk)


def write_messages(
    category: str,
    messages: Iterable[ScubaMessage],
    config: ScribeConfig,
    timestamp: Optional[int] = None,
    timeout: int = 60,
    clock: Clock = ClockImpl(),
) -> None:
    """Write a list of {scuba_type: {key: value}} messages to the given Scribe
    category, additionally adding {"time": timestamp} to the ints bucket.
    """
    logs = []
    for message in messages:
        if "time" not in message.int and timestamp is not None:
            message.int["time"] = timestamp

        logs.append(
            ScribeLog(
                category=category,
                message=json_dumps_dataclass(message),
                line_escape=False,
            ),
        )

    write_logs(
        lambda ls: write_logs_with_retries(
            ls, config=config, timeout=timeout, clock=clock
        ),
        logs,
    )
