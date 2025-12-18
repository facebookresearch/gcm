# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import operator
import time
from functools import wraps
from itertools import accumulate, chain, islice, repeat
from typing import Callable, Generator, Iterable, TypeVar, Union

from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)


class Retry(Exception):
    """Raised if a retry should be attempted."""


class OutOfRetries(Exception):
    """Raised if there are no retries remaining."""


TOut_co = TypeVar("TOut_co", covariant=True)
P = ParamSpec("P")


def exponential_backoff(
    *, initial: int = 10, base: int = 2
) -> Generator[int, None, None]:
    yield from accumulate(repeat(base), func=operator.mul, initial=initial)


def retry(
    *,
    retry_schedule_factory: Callable[[], Iterable[int]] = lambda: islice(
        exponential_backoff(), 2
    ),
    sleep: Callable[[Union[float, int]], None] = time.sleep,
) -> Callable[[Callable[P, TOut_co]], Callable[P, TOut_co]]:
    """Try a (sync) function multiple times.

    In order to signal an error should be retried, the wrapped function should raise
    `Retry`. Exceptions not derived from this type will be propagated to the caller.
    There is a subclass of `Retry`, which contains the function which
    should be used on the next try for cases when retries need to be different
    from the initial call.

    Parameters:
        retry_schedule_factory: A callable which produces an iterable object which
            yields the amount of time to sleep (in seconds) before the next
            try. The number of iterations determines the maximum number of
            times the function is called. In particular, the max number of
            times is the length of the iterable (if finite) plus 1. If `None`,
            then a default exponential backoff schedule is used with 2 retries;
            see `exponential_backoff`.
        sleep: The callable invoked before each retry for waiting the given amount of
            time.

    Raises:
        `OutOfRetries` if a retry was attempted, but the retry schedule is exhausted.

    Examples:
        Run http_post at most 3 times (2 retries), waiting 10 seconds between each try
        >>> @retry(retry_schedule_factory=lambda: islice(repeat(10), 2))
        ... def http_post():
        ...   try:
        ...     method("POST", ...)
        ...   except HTTPError as e:
        ...     raise Retry() from e

    Raises:
        OutOfRetries when the retry schedule is exhausted.
    """

    def decorator(f: Callable[P, TOut_co]) -> Callable[P, TOut_co]:
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> TOut_co:
            # signal the last try in the schedule with None, otherwise the exception
            # handling logic becomes hard to follow
            retry_schedule = chain(retry_schedule_factory(), [None])
            try_once = lambda: f(*args, **kwargs)  # noqa: E731
            for try_idx, sleep_sec in enumerate(retry_schedule):
                logger.debug(f"Try {try_idx} (zero-indexed)")
                try:
                    return try_once()
                except Retry as e:
                    logger.debug("Got retryable exception.", exc_info=True)
                    if sleep_sec is None:
                        raise OutOfRetries() from e

                    logger.debug("Using same args as initial try for next try")
                    try_once = lambda: f(*args, **kwargs)  # noqa: E731

                    sleep(sleep_sec)
            raise AssertionError(
                "Illegal state. There is always at least one try, so we must always enter the loop body which either returns, throws an exception, or continues iteration."
            )

        return wrapper

    return decorator
