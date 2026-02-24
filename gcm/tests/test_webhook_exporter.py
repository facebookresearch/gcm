# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import dataclass
from unittest.mock import create_autospec, MagicMock

import requests
from gcm.exporters.webhook import Webhook
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log


@dataclass
class SampleMetric:
    cluster: str
    value: int


@dataclass
class SampleLog:
    cluster: str
    message: str


class TestWebhook:
    def test_write_log(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.post.return_value = MagicMock(status_code=200)

        webhook = Webhook(url="http://localhost:8080/ingest", session=session)
        log = Log(
            ts=1668197951,
            message=[SampleLog(cluster="test", message="hello")],
        )
        webhook.write(
            data=log,
            additional_params=SinkAdditionalParams(data_type=DataType.LOG),
        )

        session.post.assert_called_once()
        call_kwargs = session.post.call_args
        posted_data = json.loads(call_kwargs.kwargs["data"])
        assert posted_data == [{"cluster": "test", "message": "hello"}]
        assert call_kwargs.kwargs["headers"]["Content-Type"] == "application/json"

    def test_write_metric(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.post.return_value = MagicMock(status_code=200)

        webhook = Webhook(url="http://localhost:8080/ingest", session=session)
        log = Log(
            ts=1668197951,
            message=[SampleMetric(cluster="test", value=42)],
        )
        webhook.write(
            data=log,
            additional_params=SinkAdditionalParams(data_type=DataType.METRIC),
        )

        session.post.assert_called_once()
        call_kwargs = session.post.call_args
        posted_data = json.loads(call_kwargs.kwargs["data"])
        assert posted_data == [{"cluster": "test", "value": 42}]

    def test_bearer_token_header(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.post.return_value = MagicMock(status_code=200)

        webhook = Webhook(
            url="http://localhost:8080/ingest",
            bearer_token="secret-token-123",
            session=session,
        )
        log = Log(
            ts=1668197951,
            message=[SampleLog(cluster="test", message="hello")],
        )
        webhook.write(
            data=log,
            additional_params=SinkAdditionalParams(data_type=DataType.LOG),
        )

        call_kwargs = session.post.call_args
        assert (
            call_kwargs.kwargs["headers"]["Authorization"] == "Bearer secret-token-123"
        )

    def test_no_data_type_does_not_raise(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        webhook = Webhook(url="http://localhost:8080/ingest", session=session)
        log = Log(
            ts=1668197951,
            message=[SampleLog(cluster="test", message="hello")],
        )
        webhook.write(
            data=log,
            additional_params=SinkAdditionalParams(),
        )

    def test_custom_timeout_and_ssl(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.post.return_value = MagicMock(status_code=200)

        webhook = Webhook(
            url="http://localhost:8080/ingest",
            timeout=10,
            verify_ssl=False,
            session=session,
        )
        log = Log(
            ts=1668197951,
            message=[SampleLog(cluster="test", message="hello")],
        )
        webhook.write(
            data=log,
            additional_params=SinkAdditionalParams(data_type=DataType.LOG),
        )

        call_kwargs = session.post.call_args
        assert call_kwargs.kwargs["timeout"] == 10
        assert call_kwargs.kwargs["verify"] is False
