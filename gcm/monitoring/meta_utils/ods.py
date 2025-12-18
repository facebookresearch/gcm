#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Write datapoints to ODS via GraphQL."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Callable, List, Mapping, Optional, TYPE_CHECKING, TypedDict, Union
from urllib.parse import urljoin

import requests

from gcm.monitoring.dataclass_utils import flatten_dict_factory
from gcm.monitoring.meta_utils.scribe import GRAPH_API, GRAPH_API_VERSION
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

logger = logging.getLogger(__name__)


@dataclass
class ODSConfig:
    secret_key: str
    category_id: int = 1868
    api: str = GRAPH_API
    graph_api_version: str = GRAPH_API_VERSION
    path: str = "/ods_metrics"

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


class ODSPayload(TypedDict):
    access_token: str
    datapoints: str
    category_id: int


@dataclass
class ODSData:
    entity: str
    metrics: Mapping[str, Union[int, float]]
    time: int


@typechecked
def write(
    data: List[ODSData],
    config: ODSConfig,
    *,
    timeout: int = 60,
    session: Optional[requests.Session] = None,
    num_retries: int = 3,
    will_retry: Callable[[int], None] = lambda try_idx: time.sleep(2**try_idx),
) -> None:
    """Write a nested dict of {entity: {key: value}} to ODS.

    Parameters:
        data: The list ODS data to write.
        config: ODS configuration
        timeout: Number of seconds to wait for a response from the ODS endpoint.
        session: A requests.Session object to use to send the request. If None, then
            no session object is used (i.e. plain `requests.post`)
        num_retries: The maximum number of times to retry the request if an exception
            is raised.
        will_retry: A callable to invoke when the request will be retried. It takes a
            single argument which is the index of the next try. That is, 0 is the
            initial try, 1 is the first retry, 2 is the second retry, etc.
    """
    if num_retries < 0:
        raise ValueError(
            f"Number of retries must be a non-negative integer, but got {num_retries}."
        )

    payload = get_payload(config, data)

    total_tries = num_retries + 1
    tries_remaining = total_tries
    while True:
        tries_remaining -= 1
        try:
            if session is None:
                response = requests.post(config.endpoint, json=payload, timeout=timeout)
            else:
                response = session.post(config.endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            if tries_remaining <= 0:
                raise

            logger.debug(
                f"Tries remaining: {tries_remaining}", exc_info=True, stack_info=True
            )
            will_retry(total_tries - tries_remaining)
        else:
            logger.debug(f"Succeeded after {total_tries - tries_remaining} tries")
            break


def get_payload(config: ODSConfig, data: List[ODSData]) -> ODSPayload:
    datapoints = []
    for ods_data in data:
        for key, value in ods_data.metrics.items():
            datapoints.append(
                {
                    "entity": ods_data.entity,
                    "key": key,
                    "value": value,
                    "time": ods_data.time,
                }
            )

    logger.debug(
        f"Payload of {len(datapoints)} datapoints for ODS category {config.category_id}."
    )
    return {
        "access_token": config.secret_key,
        "datapoints": json.dumps(datapoints),
        "category_id": config.category_id,
    }


def get_ods_data(
    entity: str,
    data: DataclassInstance,
    unixtime: int,
) -> ODSData:
    # TODO: clean old fcm ODS keys
    metrics_prefix = getattr(data, "prefix", "fcm.")
    new_metrics_prefix = getattr(data, "prefix", "gcm.")
    ods_data = ODSData(
        entity=entity,
        time=unixtime,
        metrics={
            metrics_prefix + metric: value
            for metric, value in asdict(data, dict_factory=flatten_dict_factory).items()
            if isinstance(value, (int, float))
        }
        | {
            new_metrics_prefix + metric: value
            for metric, value in asdict(data, dict_factory=flatten_dict_factory).items()
            if isinstance(value, (int, float))
        },
    )
    return ods_data
