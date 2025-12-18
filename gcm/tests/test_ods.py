# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest
import requests

from gcm.monitoring.clock import ClockImpl
from gcm.monitoring.meta_utils.ods import ODSConfig, ODSData, write
from pytest_mock import MockerFixture
from requests_mock import Mocker as RequestsMocker

TEST_TIME = ClockImpl().unixtime()


@pytest.fixture
def ods_config() -> ODSConfig:
    return ODSConfig(
        secret_key="app_id|secret",
        category_id=0,
    )


@pytest.mark.parametrize(
    "data",
    [
        [ODSData(entity="fake_entity", time=TEST_TIME, metrics={})],
        [
            ODSData(
                entity="fake_entity", time=TEST_TIME, metrics={"bar": 42, "baz": 100.0}
            )
        ],
    ],
)
def test_write(
    requests_mock: RequestsMocker,
    mocker: MockerFixture,
    ods_config: ODSConfig,
    data: List[ODSData],
) -> None:
    requests_mock.post(ods_config.endpoint)
    will_retry = mocker.MagicMock()

    write(data, ods_config, will_retry=will_retry)

    assert requests_mock.call_count == 1
    assert not will_retry.called


def test_write_with_retries(
    requests_mock: RequestsMocker,
    mocker: MockerFixture,
    ods_config: ODSConfig,
) -> None:
    data = [
        ODSData(entity="fake_entity", time=TEST_TIME, metrics={"bar": 42, "baz": 100.0})
    ]
    response_list: List[Dict[str, Any]] = [
        {"exc": requests.ConnectionError},
        {"status_code": 200},
    ]
    requests_mock.post(ods_config.endpoint, response_list)
    will_retry = mocker.MagicMock()

    write(data, ods_config, num_retries=1, will_retry=will_retry)

    assert requests_mock.call_count == len(response_list)
    assert will_retry.call_count == len(response_list) - 1
    will_retry.assert_has_calls(mocker.call(i) for i in range(1, len(response_list)))


def case_connection_error(requests_mock: RequestsMocker, endpoint: str) -> None:
    requests_mock.post(endpoint, exc=requests.ConnectionError)


def case_http_error(requests_mock: RequestsMocker, endpoint: str) -> None:
    requests_mock.post(endpoint, status_code=400)


PrepareMockFn = Callable[[RequestsMocker, str], None]

prepare_mock_cases: List[PrepareMockFn] = [
    case_connection_error,
    case_http_error,
]


@pytest.mark.parametrize("prepare_mock", prepare_mock_cases)
@pytest.mark.parametrize("num_retries", [0, 3])
def test_write_raises(
    requests_mock: RequestsMocker,
    mocker: MockerFixture,
    ods_config: ODSConfig,
    num_retries: int,
    prepare_mock: PrepareMockFn,
) -> None:
    data = [
        ODSData(entity="fake_entity", time=TEST_TIME, metrics={"bar": 42, "baz": 100.0})
    ]
    prepare_mock(requests_mock, ods_config.endpoint)
    will_retry = mocker.MagicMock()

    with pytest.raises(requests.RequestException):
        write(data, ods_config, num_retries=num_retries, will_retry=will_retry)

    assert requests_mock.call_count == num_retries + 1
    assert will_retry.call_count == num_retries
    will_retry.assert_has_calls(mocker.call(i) for i in range(1, num_retries + 1))


class TestODSConfig:
    @staticmethod
    def test_loads_value() -> None:
        c = ODSConfig(secret_key="app_id|secret")

        assert c.secret_key == "app_id|secret"

    @staticmethod
    def test_loads_from_path(tmp_path: Path) -> None:
        secret_path = tmp_path / "secret_file"
        with secret_path.open("w") as f:
            f.write("secret\n")

        c = ODSConfig(secret_key=str(secret_path))

        assert c.secret_key == "secret"

    @staticmethod
    def test_init_prefers_path(tmp_path: Path) -> None:
        secret_path = tmp_path / "secret"
        with secret_path.open("w") as f:
            f.write("the actual secret\n")

        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            c = ODSConfig(secret_key="secret")
        finally:
            os.chdir(cwd)

        assert c.secret_key == "the actual secret"
