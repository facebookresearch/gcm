# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any, List, Optional, Type

import pytest

from gcm.monitoring.meta_utils.scribe import (
    ScribeConfig,
    ScribeError,
    ScribeErrorWithAcks,
    ScribeLog,
    try_write_logs,
)
from requests import HTTPError, RequestException, Timeout
from requests_mock import Mocker
from typing_extensions import Protocol


@pytest.fixture
def scribe_config() -> ScribeConfig:
    return ScribeConfig(
        secret_key="test key",
    )


class MockerFactory(Protocol):
    def __call__(
        self,
        json: Any,
        *,
        status_code: HTTPStatus = ...,
        exc: Optional[RequestException] = ...,
    ) -> Mocker: ...


@pytest.fixture
def graph_api_mocker_factory(
    requests_mock: Mocker, scribe_config: ScribeConfig
) -> MockerFactory:
    def factory(
        json: Any,
        *,
        status_code: HTTPStatus = HTTPStatus.OK,
        exc: Optional[RequestException] = None,
    ) -> Mocker:
        if exc is None:
            requests_mock.post(
                scribe_config.endpoint,
                json=json,
                status_code=status_code,
            )
        else:
            requests_mock.post(scribe_config.endpoint, exc=exc)
        return requests_mock

    return factory


def scribe_log(
    *, category: str = "test", message: str, line_escape: bool = False
) -> ScribeLog:
    return ScribeLog(
        category=category,
        message=message,
        line_escape=line_escape,
    )


@pytest.mark.parametrize(
    "logs, json_response",
    [
        ([scribe_log(message="m1")], {"count": 1, "response_codes": {"0": "OK"}}),
        (
            [scribe_log(message="m1"), scribe_log(message="m2")],
            {"count": 2, "response_codes": {"0": "OK", "1": "OK"}},
        ),
    ],
)
def test_try_write_logs(
    scribe_config: ScribeConfig,
    graph_api_mocker_factory: MockerFactory,
    logs: List[ScribeLog],
    json_response: Any,
) -> None:
    mocker = graph_api_mocker_factory(json_response)

    # success is indicated by no exception
    try_write_logs(scribe_config, logs, 1)

    assert mocker.call_count == 1


@pytest.mark.parametrize(
    "json_response, status_code, endpoint_exc, expected_exc",
    [
        # Messages sent != messages written
        (
            {"count": 0, "response_codes": {"0": "ERROR"}},
            HTTPStatus.OK,
            None,
            ScribeError,
        ),
        # Not all messages acked
        (
            {"count": 0, "response_codes": {"0": "ERROR"}},
            HTTPStatus.OK,
            None,
            ScribeErrorWithAcks,
        ),
        # HTTP 404
        (
            {"count": 0, "response_codes": {"0": "ERROR"}},
            HTTPStatus.NOT_FOUND,
            None,
            HTTPError,
        ),
        # Request timeout without acks
        (
            {"count": 0, "response_codes": {"0": "TIMEOUT"}},
            HTTPStatus.OK,
            Timeout,
            Timeout,
        ),
        # Arbitrary exception when POST-ing
        (
            {"count": 0, "response_codes": {"0": "ERROR"}},
            HTTPStatus.OK,
            RequestException,
            RequestException,
        ),
    ],
)
def test_try_write_logs_bad(
    scribe_config: ScribeConfig,
    graph_api_mocker_factory: MockerFactory,
    json_response: Any,
    status_code: HTTPStatus,
    endpoint_exc: Optional[RequestException],
    expected_exc: Type[Exception],
) -> None:
    mocker = graph_api_mocker_factory(
        json_response, status_code=status_code, exc=endpoint_exc
    )

    with pytest.raises(expected_exc):
        try_write_logs(scribe_config, [scribe_log(message="m1")], 1)

    if isinstance(expected_exc, ScribeErrorWithAcks):
        assert not all(expected_exc.acks)
    assert mocker.call_count == 1


class TestScribeConfig:
    @staticmethod
    def test_loads_value() -> None:
        c = ScribeConfig(secret_key="app_id|secret")

        assert c.secret_key == "app_id|secret"

    @staticmethod
    def test_loads_from_path(tmp_path: Path) -> None:
        secret_path = tmp_path / "secret"
        with secret_path.open("w") as f:
            f.write("secret\n")

        c = ScribeConfig(secret_key=str(secret_path))

        assert c.secret_key == "secret"

    @staticmethod
    def test_init_prefers_path(tmp_path: Path) -> None:
        secret_path = tmp_path / "secret"
        with secret_path.open("w") as f:
            f.write("the actual secret\n")

        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            c = ScribeConfig(secret_key="secret")
        finally:
            os.chdir(cwd)

        assert c.secret_key == "the actual secret"
