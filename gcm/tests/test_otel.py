# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log

if TYPE_CHECKING:
    from gcm.exporters.otel import Otel


@dataclass
class _OtelDummyMsg:
    field_a: int = 7


@dataclass
class _OtelBooleanMetricMsg:
    healthy: bool = True


@dataclass
class _OtelOptionalMetricMsg:
    value: int | None


class _CaptureHandler(logging.Handler):
    """Attached to Otel.otel_logger to record what the OTLP handler would
    receive without sending real network traffic. Behavioral substitute for
    monkey-patching the OTLP transport."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestOtelLoggerBehavior:
    """Behavioral guards: a sibling gcm.* log record MUST NOT reach the otel
    emit handler (regression for the propagate=False fix); an explicit
    sink.write MUST reach it (positive control). Together they fail if the
    isolation logger is ever pointed back at 'gcm' or propagate is re-enabled."""

    @staticmethod
    def _make_otel() -> "Otel":
        from gcm.exporters.otel import Otel

        return Otel(
            log_resource_attributes=None,
            metric_resource_attributes=None,
            otel_endpoint="http://localhost:4318",
            otel_timeout=1,
        )

    def test_unrelated_gcm_logger_does_not_emit_to_otel(self) -> None:
        otel = self._make_otel()
        capture = _CaptureHandler()
        otel.otel_logger.addHandler(capture)
        try:
            sibling = logging.getLogger("gcm.monitoring.dataclass_utils")
            sibling.warning("Missing field_name=foo")
            assert capture.records == []
        finally:
            otel.otel_logger.removeHandler(capture)
            otel.shutdown()

    def test_gcm_logger_emits_to_otel(self) -> None:
        otel = self._make_otel()
        capture = _CaptureHandler()
        otel.otel_logger.addHandler(capture)
        try:
            otel.write(
                Log(ts=42, message=[_OtelDummyMsg(field_a=7)]),
                SinkAdditionalParams(data_type=DataType.LOG),
            )
            assert len(capture.records) == 1
            extra = capture.records[0].__dict__
            assert extra.get("field_a") == 7
            assert extra.get("time") == 42
        finally:
            otel.otel_logger.removeHandler(capture)
            otel.shutdown()

    def test_boolean_metric_is_exported_as_integer(self) -> None:
        otel = self._make_otel()
        gauge = MagicMock()
        otel.meter = MagicMock()
        otel.meter.create_gauge.return_value = gauge
        try:
            otel.write(
                Log(ts=42, message=[_OtelBooleanMetricMsg(healthy=True)]),
                SinkAdditionalParams(data_type=DataType.METRIC),
            )
            gauge.set.assert_called_once_with(amount=1)
        finally:
            otel.shutdown()

    def test_invalid_metric_value_is_skipped_after_instrument_creation(self) -> None:
        otel = self._make_otel()
        gauge = MagicMock()
        otel.meter = MagicMock()
        otel.meter.create_gauge.return_value = gauge
        try:
            otel.write(
                Log(
                    ts=42,
                    message=[
                        _OtelOptionalMetricMsg(value=7),
                        _OtelOptionalMetricMsg(value=None),
                    ],
                ),
                SinkAdditionalParams(data_type=DataType.METRIC),
            )
            gauge.set.assert_called_once_with(amount=7)
        finally:
            otel.shutdown()


class TestOtelLoggerIsolation:
    """Regression: an earlier version of the otel sink attached its
    LoggingHandler to the `"gcm"` logger. Python logging propagation then
    made every `gcm.*` log record (e.g. the
    `Missing field_name='derived_cluster'` warnings from
    `gcm.monitoring.dataclass_utils`) bubble up to the handler and emit as
    a null-data row into whatever Scuba dataset the otel sink was targeting.

    Observed impact before the fix (24h sample):
    - `fair_sacct_running`: 637,929 / 713,988 rows (89.3%) were null-data
      leakage; most attributed to `gcm/exporters/otel.py:_write_log` itself
      (the handler recursing on its own emitted log records, self-amplifying).
    - `fair_sdiag`: 80 / 200 rows (40%) leaked from
      `gcm/monitoring/dataclass_utils.py:instantiate_dataclass`.
    - Other otel-targeted tables (`fair_sacct`, `fair_scontrol_data`, etc.)
      were unaffected because their publish paths don't trigger `gcm.*`
      logging in the otel write window.

    Fix: dedicated leaf logger `_gcm_otel_emit` with `propagate=False`.
    Only explicit `self.otel_logger.info("", extra=...)` writes reach the
    otel handler."""

    def test_otel_logger_does_not_capture_gcm_logs(self) -> None:
        from gcm.exporters.otel import Otel

        # Otel ctor requires an endpoint; provide via kwargs (no real network
        # traffic in the test -- the handler is on a separate logger).
        otel = Otel(
            log_resource_attributes=None,
            metric_resource_attributes=None,
            otel_endpoint="http://localhost:4318",
            otel_timeout=1,
        )

        try:
            # The sink's emit logger MUST NOT be the "gcm" logger.
            assert otel.otel_logger.name != "gcm"
            # And it MUST have propagate disabled so records on this logger
            # don't bubble up to ancestors with handlers.
            assert otel.otel_logger.propagate is False

            # Verify the converse: a child of "gcm" walking up its parent
            # chain does NOT find the otel handler. If propagation were
            # broken the handler would appear in this chain.
            gcm_child = logging.getLogger("gcm.monitoring.test_isolation")
            child_handler_chain: list[logging.Handler] = []
            cur: logging.Logger | None = gcm_child
            while cur is not None:
                child_handler_chain.extend(cur.handlers)
                cur = cur.parent
            assert otel.otel_logger.handlers[0] not in child_handler_chain
        finally:
            otel.shutdown()
