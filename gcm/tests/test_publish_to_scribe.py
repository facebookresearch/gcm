# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import cast
from unittest.mock import create_autospec, MagicMock

import pytest
import requests

from gcm.monitoring.meta_utils.scribe import ScribeConfig, ScribeError, write_messages
from gcm.monitoring.meta_utils.scuba import ScubaMessage
from gcm.tests.fakes import FakeClock


@pytest.fixture
def scribe_config() -> ScribeConfig:
    return ScribeConfig(
        secret_key="",
        path="",
        session=create_autospec(requests.Session, instance=True),
    )


class TestPublishToScribe:
    @staticmethod
    def test_publish_all_acked(scribe_config: ScribeConfig) -> None:
        expected = {"count": 1, "response_codes": {"0": "OK"}}
        response_stub = create_autospec(requests.Response, instance=True)
        response_stub.json.return_value = expected
        # SAFETY: session is specced out; see `scribe_config`
        session_stub = cast(MagicMock, scribe_config.session)
        session_stub.post.return_value = response_stub

        write_messages(
            "test_category",
            [ScubaMessage()],
            config=scribe_config,
            timestamp=0,
            clock=FakeClock(),
        )

        assert session_stub.post.call_count == 1
        response_stub.json.assert_called_once_with()

    @staticmethod
    def test_publish_fail_once(scribe_config: ScribeConfig) -> None:
        response_initial = {"count": 1, "response_codes": {"0": "OK", "1": "ERROR"}}
        response_final = {"count": 1, "response_codes": {"0": "OK"}}
        response_stub = create_autospec(requests.Response, instance=True)
        response_stub.json.side_effect = [response_initial, response_final]
        # SAFETY: session is specced out; see `scribe_config`
        session_stub = cast(MagicMock, scribe_config.session)
        session_stub.post.return_value = response_stub

        write_messages(
            "test_category",
            [ScubaMessage(), ScubaMessage()],
            config=scribe_config,
            timestamp=0,
            clock=FakeClock(),
        )

        assert session_stub.post.call_count == 2
        assert response_stub.json.call_count == 2

    @staticmethod
    def test_publish_fail_all(scribe_config: ScribeConfig) -> None:
        expected = {
            "count": 0,
            "response_codes": {"0": "ERROR", "1": "ERROR", "2": "ERROR"},
        }
        response_stub = create_autospec(requests.Response, instance=True)
        response_stub.json.return_value = expected
        # SAFETY: session is specced out; see `scribe_config`
        session_stub = cast(MagicMock, scribe_config.session)
        session_stub.post.return_value = response_stub
        num_tries = 3

        with pytest.raises(ScribeError):
            write_messages(
                "test_category",
                [ScubaMessage(), ScubaMessage(), ScubaMessage()],
                config=scribe_config,
                timestamp=0,
                clock=FakeClock(),
            )

        assert session_stub.post.call_count == num_tries
        assert response_stub.json.call_count == num_tries

    @staticmethod
    def test_publish_no_json_once(scribe_config: ScribeConfig) -> None:
        expected = {"count": 2, "response_codes": {"0": "OK", "1": "OK"}}
        response_stub = create_autospec(requests.Response, instance=True)
        response_stub.json.side_effect = [ValueError, expected]
        # SAFETY: session is specced out; see `scribe_config`
        session_stub = cast(MagicMock, scribe_config.session)
        session_stub.post.return_value = response_stub
        num_tries = 2

        write_messages(
            "test_category",
            [ScubaMessage(), ScubaMessage()],
            config=scribe_config,
            timestamp=0,
            clock=FakeClock(),
        )

        assert session_stub.post.call_count == num_tries
        assert response_stub.json.call_count == num_tries
