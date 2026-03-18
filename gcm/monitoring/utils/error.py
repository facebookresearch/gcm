#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Miscellaneous error-handling helpers."""

import logging
import traceback
from functools import wraps
from typing import Callable, Optional, overload, TypeVar, Union

from typing_extensions import ParamSpec

_T = TypeVar("_T")
_Tr_co = TypeVar("_Tr_co", covariant=True)
_P = ParamSpec("_P")


def safe_call(
    func: Callable[[], _T],
    *catch: type[BaseException],
    logger_name: Optional[str] = None,
) -> Optional[_T]:
    """Call *func* and return None if it raises a matching exception.

    If no exception types are passed, catches all ``Exception`` subclasses.
    Failures are logged at WARNING level.
    """
    catch_types: tuple[type[BaseException], ...] = catch or (Exception,)
    try:
        return func()
    except catch_types:
        logging.getLogger(logger_name or __name__).warning(
            "safe_call: %s failed", func, exc_info=True
        )
        return None


def fmt_exc_for_log() -> str:
    parts = traceback.format_exc(-1).strip().split("\n")
    return "{}: {}".format(parts[-1].strip(), parts[1].strip())


@overload
def log_error(
    logger_name: str,
) -> Callable[[Callable[_P, _Tr_co]], Callable[_P, Optional[_Tr_co]]]: ...


@overload
def log_error(
    logger_name: str, return_on_error: _T = ...
) -> Callable[[Callable[_P, _Tr_co]], Callable[_P, Union[None, _T, _Tr_co]]]: ...


def log_error(
    logger_name: str,
    return_on_error: Optional[_T] = None,
) -> Callable[[Callable[_P, _Tr_co]], Callable[_P, Union[None, _T, _Tr_co]]]:
    """Decorator which catches and writes all exceptions to the given logger."""

    def decorator(f: Callable[_P, _Tr_co]) -> Callable[_P, Union[None, _T, _Tr_co]]:
        @wraps(f)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Union[None, _T, _Tr_co]:
            try:
                return f(*args, **kwargs)
            except Exception:
                logging.getLogger(logger_name).exception("An exception occurred")
                return return_on_error

        return wrapper

    return decorator
