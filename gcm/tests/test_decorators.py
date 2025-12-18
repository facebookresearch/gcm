# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import time
from typing import List
from unittest.mock import call, create_autospec, MagicMock

import pytest

from gcm.monitoring.decorators import OutOfRetries, Retry, retry


class TestRetry:
    @staticmethod
    def test_no_throw() -> None:
        f = MagicMock()
        retryable_f = retry(retry_schedule_factory=lambda: [10])(f)

        rv = retryable_f(1, "foo", bar=None)

        assert rv is f.return_value
        f.assert_called_once_with(1, "foo", bar=None)

    @staticmethod
    def test_does_retry() -> None:
        stub_sleep = create_autospec(spec=time.sleep)
        f = MagicMock()
        f.side_effect = [Retry(), "return value"]
        retryable_f = retry(retry_schedule_factory=lambda: [10], sleep=stub_sleep)(f)

        rv = retryable_f(1, "foo", bar=None)

        assert rv == "return value"
        assert f.call_args_list == [
            call(1, "foo", bar=None),
            call(1, "foo", bar=None),
        ]
        stub_sleep.assert_called_once_with(10)

    @staticmethod
    @pytest.mark.parametrize(
        "side_effect, retry_schedule",
        [
            ([Retry()], []),
            ([Retry(), Retry()], [10]),
        ],
    )
    def test_throws_when_out_of_retries(
        side_effect: List[Exception], retry_schedule: List[int]
    ) -> None:
        stub_sleep = create_autospec(spec=time.sleep)
        f = MagicMock()
        f.side_effect = side_effect
        retryable_f = retry(
            retry_schedule_factory=lambda: retry_schedule, sleep=stub_sleep
        )(f)

        with pytest.raises(OutOfRetries):
            retryable_f(1, "foo", bar=None)

        n_tries = len(retry_schedule) + 1
        assert f.call_args_list == [call(1, "foo", bar=None)] * n_tries
        assert stub_sleep.call_args_list == [call(x) for x in retry_schedule]

    @staticmethod
    def test_propagates_non_retryable_exception() -> None:
        class NonRetryableException(Exception):
            pass

        stub_sleep = create_autospec(spec=time.sleep)
        f = MagicMock()
        f.side_effect = NonRetryableException()
        retryable_f = retry(retry_schedule_factory=lambda: [10], sleep=stub_sleep)(f)

        with pytest.raises(NonRetryableException):
            retryable_f(1, "foo", bar=None)

        f.assert_called_once_with(1, "foo", bar=None)
        stub_sleep.assert_not_called()
