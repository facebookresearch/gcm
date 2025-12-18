# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from dataclasses import asdict

from gcm.exporters import register

from gcm.monitoring.dataclass_utils import (
    flatten_dict_factory,
    remove_none_dict_factory,
)
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log

logger = logging.getLogger(__name__)


@register("stdout")
class Stdout:
    """Write data to stdout."""

    def _write_log(self, data: Log) -> None:
        print(
            json.dumps(
                [
                    asdict(message, dict_factory=remove_none_dict_factory)
                    for message in data.message
                ]
            )
        )

    def _write_metric(self, data: Log) -> None:
        print(
            json.dumps(
                [
                    asdict(message, dict_factory=flatten_dict_factory)
                    for message in data.message
                ]
            )
        )

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
                f"Stdout writes requires data_type to be specified: {additional_params}"
            )
            return
