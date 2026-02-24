# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from dataclasses import asdict
from typing import Optional

import requests
from gcm.exporters import register
from gcm.monitoring.dataclass_utils import (
    flatten_dict_factory,
    remove_none_dict_factory,
)
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log

logger = logging.getLogger(__name__)


@register("webhook")
class Webhook:
    """Send data to an HTTP webhook endpoint."""

    def __init__(
        self,
        *,
        url: str,
        timeout: int = 30,
        bearer_token: Optional[str] = None,
        verify_ssl: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = session or requests.Session()
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        if bearer_token is not None:
            self.headers["Authorization"] = f"Bearer {bearer_token}"

    def _post(self, payload: str) -> None:
        response = self.session.post(
            self.url,
            data=payload,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()

    def _write_log(self, data: Log) -> None:
        payload = json.dumps(
            [
                asdict(message, dict_factory=remove_none_dict_factory)
                for message in data.message
            ]
        )
        self._post(payload)

    def _write_metric(self, data: Log) -> None:
        payload = json.dumps(
            [
                asdict(message, dict_factory=flatten_dict_factory)
                for message in data.message
            ]
        )
        self._post(payload)

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        if additional_params.data_type:
            if additional_params.data_type is DataType.LOG:
                return self._write_log(data)
            elif additional_params.data_type is DataType.METRIC:
                return self._write_metric(data)
            else:
                logger.error(
                    f"We expected log or metrics, but got {additional_params.data_type}"
                )
        else:
            logger.error(
                f"Webhook writes requires data_type to be specified: {additional_params}"
            )
            return
