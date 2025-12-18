# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import re
from itertools import product
from typing import Any

from gcm.monitoring.utils.parsing.combinators import (
    at_least_zero,
    begins_with,
    chain,
    discard_result,
    first_of,
    Parser,
    ParseResult,
)

from typeguard import typechecked

logger = logging.getLogger(__name__)


def split_outer_commas(s: str) -> list[str]:
    """
    Split a Slurm nodelist string on commas, but only at bracket level zero.
    This ensures that commas inside bracketed range expressions (e.g. host[01,02])
    are not treated as delimiters for separate nodes.
    Example:
        split_outer_commas('nodeA,nodeB-[01,02]') -> ['nodeA', 'nodeB-[01,02]']
    """
    parts = []
    bracket_level = 0
    last = 0
    for i, c in enumerate(s):
        if c == "[":
            bracket_level += 1
        elif c == "]":
            bracket_level -= 1
        elif c == "," and bracket_level == 0:
            parts.append(s[last:i].strip())
            last = i + 1
    parts.append(s[last:].strip())
    return [p for p in parts if p]


def nodelist_parser(s: str) -> ParseResult[str]:
    """
    A Slurm nodelist can be:
        1. a single nodename (see `single_node`)
        2. a node range expression (see `node_range_expression`)
        3. a comma-separated list of these, where commas are only split at bracket level zero.

    Handles both single nodes and bracketed range expressions, supporting
    comma-separated lists while respecting bracket nesting.
    """
    if not s:
        return None, s
    result = []
    # Split input into node expressions, handling commas inside brackets
    for part in split_outer_commas(s):
        # Try to parse each part as either a node range or a single node
        parsed, leftover = first_of([node_range_expression(), single_node()])(part)
        # If parsing fails or there is leftover unparsed string, fail
        if parsed is None or leftover:
            return None, s
        # Add parsed nodes to result
        result.extend(parsed)
    return result, ""


def nodelist() -> Parser[str]:
    """
    Returns a parser for Slurm nodelist strings.
    See nodelist_parser for details.
    """
    return nodelist_parser


def single_node() -> Parser[str]:
    """A single nodename. Currently, only hostnames are supported (e.g. what would be
    returned by `hostname -s`).

    For details, refer to https://slurm.schedmd.com/slurm.conf.html#OPT_NodeName
    """

    def parser(s: str) -> ParseResult[str]:
        m = re.match(r"^([A-Za-z0-9])([A-Za-z0-9\-])*([A-Za-z0-9])$", s)
        if m is None:
            return None, s

        return [m.group(0)], ""

    return parser


def node_range_expression() -> Parser[str]:
    """Expand a Slurm node range expression into a list of names.

    For details, refer to https://github.com/SchedMD/slurm/blob/9931aec3dd2c9885e4a1e139e3a2b7ef4f81351d/src/common/hostlist.h#L101-L140

    Roughly speaking, a node range expression is:
        <name_1><expr_1>[<name_2><expr_2>[...[<name_n><expr_n>]]]
    where
        * <name_1> is either empty of a valid hostname prefix, i.e. the first character
          is alphanumeric, the rest are alphanumeric or hyphen (RFC 952, RFC 1123),
        * <name_i>, i > 1 is any number of alphanumeric or hyphens (may be empty), and
        * <expr_i> is
            '[' <m> '-' <n> ']'
          where <m> and <n> are integers such that m <= n. Leading zeroes may be given
          to indicate padding.

    Examples:
        >>> p = node_range_expression()
        >>> p("a[0-2]")
        ... (["a0", "a1", "a2"], "")
        >>> p("a[00-02]")
        ... (["a00", "a01", "a02"])
        >>> p("a[0-2][3-5]")
        ... (["a03", "a04", "a05", "a13", "a14", "a15", "a23", "a24", "a25"], "")
        >>> p("h200-183-[001-003]")
        ... (["h200-183-001", "h200-183-002", "h200-183-003"], "")
    """

    def parser_(s: str) -> ParseResult[str]:
        if s == "":
            return [], ""

        intermediate_range_expression_parser = chain(
            [partial_hostname(), range_expression()]
        )
        parsed, rest = intermediate_range_expression_parser(s)
        if parsed is None:
            return None, s

        parsed_rest, unparsed = parser_(rest)
        if parsed_rest is None:
            return None, s

        prefix, *suffixes = parsed
        if len(parsed_rest) == 0:
            return [prefix + suffix for suffix in suffixes], unparsed

        return [
            prefix + suffix + rest for suffix, rest in product(suffixes, parsed_rest)
        ], unparsed

    def parser(s: str) -> ParseResult[str]:
        single_range_expression_parser = chain([hostname_prefix(), range_expression()])
        parsed, rest = single_range_expression_parser(s)
        if parsed is None:
            return None, s

        parsed_rest, unparsed = parser_(rest)
        if parsed_rest is None:
            return None, s

        prefix, *suffixes = parsed
        if len(parsed_rest) == 0:
            return [prefix + suffix for suffix in suffixes], unparsed

        return [
            prefix + suffix + rest for suffix, rest in product(suffixes, parsed_rest)
        ], unparsed

    return parser


def hostname_prefix() -> Parser[str]:
    def parser(s: str) -> ParseResult[str]:
        # Use hostname_start_end_char which now handles bracket expressions
        p = chain([hostname_start_end_char(), partial_hostname()])
        parsed, rest = p(s)
        if parsed is None:
            return None, s
        return ["".join(parsed)], rest

    return parser


def hostname_start_end_char() -> Parser[str]:
    @typechecked
    def parser(s: str) -> ParseResult[str]:
        """Parse hostname part of a node expression.

        This function handles two cases:
        1. If the string contains a '[' character (indicating a range expression),
           it returns everything before the '[' as the prefix.
        2. Otherwise, it returns just the first character of the hostname.

        In both cases, it ensures the hostname follows RFC 952/1123 standards.
        """
        if not s:
            return None, s

        # Handle bracket expressions - return entire prefix before bracket
        # This handles cases like "host-[1-3]" where the hyphen is part of the hostname
        bracket_pos = s.find("[")
        if bracket_pos > 0:
            prefix = s[:bracket_pos]
            # Validate hostname prefix (RFC 952/1123): alphanumeric first char,
            # rest can be alphanumeric or hyphens
            if re.match(r"^[A-Za-z0-9][A-Za-z0-9\-]*$", prefix):
                return [prefix], s[bracket_pos:]
            return None, s

        # Standard case - return just first character
        # This is used for hostnames without brackets and will be chained with partial_hostname()
        m = re.match(r"^([A-Za-z0-9])(.*)$", s)
        if m is None:
            return None, s
        return [m.group(1)], m.group(2)

    return parser


def partial_hostname() -> Parser[str]:
    @typechecked
    def parser(s: str) -> ParseResult[str]:
        pattern = re.compile(r"^([A-Za-z0-9-]*)(.*)$")
        m = pattern.match(s)
        if m is None:
            return None, s

        name = m.group(1)
        rest = m.group(2)
        return [name], rest

    return parser


@typechecked
def range_expression() -> Parser[str]:
    return chain(
        [
            discard_result(begins_with("[")),
            range_expression_element(),
            at_least_zero(
                chain(
                    [
                        discard_result(begins_with(",")),
                        range_expression_element(),
                    ]
                ),
            ),
            discard_result(begins_with("]")),
        ]
    )


def range_expression_element() -> Parser[str]:
    def parser(s: str) -> ParseResult[str]:
        range_pattern = re.compile(r"^([0-9]+)-([0-9]+)(.*)$")
        single_number_pattern = re.compile(r"^(0*)([0-9]+)(.*)$")

        m = range_pattern.match(s)
        if m is None:
            single_match = single_number_pattern.match(s)
            if single_match is None:
                return None, s

            # leading zeroes + digits, rest
            return [
                f"{single_match.group(1)}{single_match.group(2)}"
            ], single_match.group(3)

        start = m.group(1)
        end = m.group(2)
        rest = m.group(3)
        if int(start) > int(end):
            logger.debug(f"Parse failed; {start} > {end}")
            return None, s

        start_match = single_number_pattern.match(start)
        if start_match is None:
            return None, s

        leading_zeroes = _str_or_throw(start_match.group(1))
        remaining_digits = _str_or_throw(start_match.group(2))

        fmt = f"{{num:0{len(leading_zeroes) + len(remaining_digits)}d}}"
        return [fmt.format(num=i) for i in range(int(start), int(end) + 1)], rest

    return parser


def _str_or_throw(x: Any) -> str:
    if not isinstance(x, str):
        raise TypeError(f"Expected str but got '{type(x).__name__}'")
    return x
