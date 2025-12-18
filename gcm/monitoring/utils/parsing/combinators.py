# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Utilities for parsing strings.

A parser is a function str -> (list<T> | None, str) which takes an arbitrary
string and returns a tuple where the first element corresponds to the parsed
result and the second corresponds to the unconsumed part of the input string.
The parsed result is a list<T> on success and None on failure.
"""

from typing import Any, Callable, List, Optional, Tuple, TypeVar

from typing_extensions import Protocol

_TResult = TypeVar("_TResult")
ParseResult = Tuple[Optional[List[_TResult]], str]
Parser = Callable[[str], ParseResult[_TResult]]
NonNullParseResult = Tuple[List[_TResult], str]
NonNullParser = Callable[[str], NonNullParseResult[_TResult]]


def begins_with(prefix: str) -> Parser[str]:
    """Returns a parser which parses a string with the given prefix"""

    def begins_with_parser(s: str) -> ParseResult[str]:
        if s.startswith(prefix):
            return [prefix], s[len(prefix) :]  # noqa: E203
        else:
            return None, s

    return begins_with_parser


_TIn = TypeVar("_TIn")
_TOut = TypeVar("_TOut")


def discard_result(parser: Parser[_TIn]) -> Parser[_TOut]:
    """Returns a parser which discards the parsed result. It fails if the given
    parser fails.
    """

    def discard_result_parser(s: str) -> ParseResult[_TResult]:
        parsed, rest = parser(s)
        if parsed is None:
            return None, s
        else:
            return [], rest

    return discard_result_parser


_T_co = TypeVar("_T_co", covariant=True)


class Addable(Protocol[_T_co]):
    def __add__(self, other: Any) -> _T_co: ...


_TAddable = TypeVar("_TAddable", bound=Addable)


def at_least_zero(parser: Parser[_TAddable]) -> NonNullParser[_TAddable]:
    """Returns a parser which runs a given parser until failure and returns
    the aggregated results.
    """

    def at_least_zero_parser(s: str) -> NonNullParseResult[_TAddable]:
        parsed, rest = parser(s)
        if parsed is None:
            return [], rest
        else:
            parsed_, rest_ = at_least_zero_parser(rest)
            return parsed + parsed_, rest_

    return at_least_zero_parser


def first_of(parsers: List[Parser]) -> Parser:
    """Returns a parser which runs a list of parsers and greedily returns
    the first successful parse. Fails if all of the given parsers fail.
    """

    def first_of_parser(s: str) -> ParseResult:
        for parser in parsers:
            parsed, rest = parser(s)
            if parsed is not None:
                return parsed, rest
        # if no parser succeeded, then fail
        return None, s

    return first_of_parser


def at_least_one(parser: Parser[_TAddable]) -> Parser[_TAddable]:
    """Returns a parser which runs the given parser at least once. If the
    parser fails on the first run, then fail. Otherwise, return the aggregated
    result.
    """
    at_least_zero_parser = at_least_zero(parser)

    def at_least_one_parser(s: str) -> ParseResult[_TAddable]:
        parsed, rest = at_least_zero_parser(s)
        if len(parsed) == 0:
            return None, s
        else:
            return parsed, rest

    return at_least_one_parser


def chain(parsers: List[Parser]) -> Parser:
    """Returns a parser which runs a list of parsers sequentially and
    aggregates the results. Fails if any parser fails.
    """

    def chain_parser(s: str) -> ParseResult:
        acc, rest = parsers[0](s)
        if acc is None:
            return None, s

        for parser in parsers[1:]:
            parsed, rest = parser(rest)
            if parsed is None:
                return None, s
            acc.extend(parsed)
        return acc, rest

    return chain_parser
