# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
from dataclasses import asdict, fields
from typing import Any, cast, Dict, Optional

from gcm.exporters import register

from gcm.monitoring.dataclass_utils import flatten_dict_factory
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log

from omegaconf import DictConfig, OmegaConf
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import _Gauge
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from opentelemetry.sdk.resources import (  # type: ignore[attr-defined]
    Resource,
    SERVICE_NAME,
)

from typing_extensions import Never

logger = logging.getLogger(__name__)


def otel_log_init(
    resource_attributes: Optional[DictConfig], otel_endpoint: str, otel_timeout: int
) -> LoggerProvider:
    resource_attrs_dict: Dict[str, Any] = cast(
        Dict[str, Any],
        (
            OmegaConf.to_container(resource_attributes, resolve=True)
            if resource_attributes is not None
            else {}
        ),
    )

    resource = Resource(attributes={**resource_attrs_dict})

    logger_provider = LoggerProvider(resource=resource)
    exporter = OTLPLogExporter(
        endpoint=otel_endpoint,
        timeout=otel_timeout,
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    set_logger_provider(logger_provider)
    return logger_provider


def otel_metric_init(
    resource_attributes: Optional[DictConfig], otel_endpoint: str, otel_timeout: int
) -> Meter:
    resource_attrs_dict: Dict[str, Any] = cast(
        Dict[str, Any],
        (
            OmegaConf.to_container(resource_attributes, resolve=True)
            if resource_attributes is not None
            else {}
        ),
    )

    resource = Resource(attributes={**resource_attrs_dict})
    exporter = OTLPMetricExporter(
        endpoint=otel_endpoint,
        timeout=otel_timeout,
    )
    reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=60000, export_timeout_millis=5000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    return meter_provider.get_meter("gcm-meter")


def get_otel_endpoint(otel_endpoint: Optional[str]) -> str:
    if otel_endpoint is None:
        if "OTEL_EXPORTER_OTLP_ENDPOINT" not in os.environ:
            raise ValueError(
                "could not find a otel exporter otlp endpoint, you can set the environment variable OTEL_EXPORTER_OTLP_ENDPOINT."
            )
        return os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]
    return otel_endpoint


def get_otel_timeout(otel_timeout: Optional[int]) -> int:
    if otel_timeout is None:
        if "OTEL_EXPORTER_OTLP_TIMEOUT" not in os.environ:
            raise ValueError(
                "could not find a otel exporter otlp endpoint, you can set the environment variable OTEL_EXPORTER_OTLP_TIMEOUT."
            )
        return int(os.environ["OTEL_EXPORTER_OTLP_TIMEOUT"])
    return otel_timeout


@register("otel")
class Otel:
    def __init__(
        self,
        *,
        log_resource_attributes: Optional[DictConfig] = None,
        metric_resource_attributes: Optional[DictConfig] = None,
        otel_endpoint: Optional[str] = None,
        otel_timeout: Optional[int] = None,
    ):
        endpoint = get_otel_endpoint(otel_endpoint)
        timeout = get_otel_timeout(otel_timeout)
        for attributes in [log_resource_attributes, metric_resource_attributes]:
            if attributes is not None:
                attributes[SERVICE_NAME] = "gcm"

        logger_provider = otel_log_init(
            log_resource_attributes, endpoint + "/v1/logs", timeout
        )
        self.otel_logger = logging.getLogger("gcm")
        otel_handler = LoggingHandler(
            level=logging._nameToLevel["INFO"], logger_provider=logger_provider
        )
        self.otel_logger.setLevel(logging.INFO)
        self.otel_logger.addHandler(otel_handler)

        self.meter = otel_metric_init(
            metric_resource_attributes, endpoint + "/v1/metrics", timeout
        )
        self.metrics_instruments: dict[str, _Gauge] = {}

    def assert_never(self, x: Never) -> Never:
        raise AssertionError(f"Unhandled type: {type(x).__name__}")

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
                    f"We expected log or metric, but got {additional_params.data_type}"
                )
                self.assert_never(additional_params.data_type)
        else:
            logger.error(
                f"OTel writes requires data_type to be specified: {additional_params}"
            )
            return

    def _write_metric(self, data: Log) -> None:
        for message in data.message:
            for field in fields(message):
                metric_name = field.name
                metric_value = getattr(message, metric_name)

                if metric_name not in self.metrics_instruments:
                    if not isinstance(metric_value, int | float):
                        logger.warning(
                            f"Unsupported data type for OTel logging: {type(metric_value)}, ignoring metric {metric_name}"
                        )
                        continue
                    self.metrics_instruments[metric_name] = self.meter.create_gauge(
                        metric_name, description=metric_name
                    )

                self.metrics_instruments[metric_name].set(
                    amount=metric_value,
                )

    def _write_log(self, data: Log) -> None:
        for message in data.message:
            msg = asdict(message, dict_factory=flatten_dict_factory)
            msg["time"] = data.ts
            self.otel_logger.info("", extra=msg)
