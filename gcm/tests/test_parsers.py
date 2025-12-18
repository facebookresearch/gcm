# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for parsers"""

import unittest
from typing import Type

import pytest

from gcm.monitoring.slurm.nodelist_parsers import (
    node_range_expression,
    nodelist,
    range_expression,
    range_expression_element,
)
from gcm.monitoring.slurm.parsing import parse_gres, parse_tres, parse_value_from_tres
from gcm.monitoring.utils.parsing.combinators import (
    at_least_one,
    at_least_zero,
    begins_with,
    chain,
    discard_result,
    first_of,
    ParseResult,
)
from typeguard import typechecked


class TestParsingUtils(unittest.TestCase):
    def test_begins_with(self) -> None:
        test_str = "hello world!"
        parser1 = begins_with("hello")
        parser2 = begins_with("hell")
        parser3 = begins_with("ello")
        parser4 = begins_with("helo")
        parser5 = begins_with("")

        result1, rest = parser1(test_str)
        self.assertEqual(result1, ["hello"])
        self.assertEqual(rest, " world!")

        result2, rest = parser2(test_str)
        self.assertEqual(result2, ["hell"])
        self.assertEqual(rest, "o world!")

        result3, rest = parser3(test_str)
        self.assertIsNone(result3)
        self.assertEqual(rest, test_str)

        result4, rest = parser4(test_str)
        self.assertIsNone(result4)
        self.assertEqual(rest, test_str)

        result5, rest = parser5(test_str)
        self.assertEqual(result5, [""])
        self.assertEqual(rest, test_str)

    def test_discard_result(self) -> None:
        test_str = "hello world!"
        # Type doesn't matter in this case
        parser1 = discard_result(begins_with("hello"))  # type: ignore[var-annotated]
        parser2 = discard_result(begins_with("ello"))  # type: ignore[var-annotated]

        result1, rest = parser1(test_str)
        self.assertEqual(result1, [])
        self.assertEqual(rest, " world!")

        result2, rest = parser2(test_str)
        self.assertIsNone(result2)
        self.assertEqual(rest, test_str)

    def test_at_least_zero(self) -> None:
        test_str = "abc" * 3
        parser1 = at_least_zero(begins_with("cde"))
        parser2 = at_least_zero(begins_with("abc"))

        result1, rest = parser1(test_str)
        self.assertEqual(result1, [])
        self.assertEqual(rest, test_str)

        result2, rest = parser2(test_str)
        self.assertEqual(result2, ["abc"] * 3)
        self.assertEqual(rest, "")

    def test_at_least_one(self) -> None:
        test_str = "abc" * 3
        parser1 = at_least_one(begins_with("ab"))
        parser2 = at_least_one(begins_with("abcd"))

        (
            result1,
            rest,
        ) = parser1(test_str)
        self.assertEqual(result1, ["ab"])
        self.assertEqual(rest, "cabcabc")

        result2, rest = parser2(test_str)
        self.assertIsNone(result2)
        self.assertEqual(rest, test_str)

    def test_first_of(self) -> None:
        test_str = "abc"
        test_str2 = "def"
        parser1 = begins_with("ab")
        parser2 = begins_with("abc")

        result1, rest = first_of([parser1, parser2])(test_str)
        self.assertEqual(result1, ["ab"])
        self.assertEqual(rest, "c")

        result2, rest = first_of([parser2, parser1])(test_str)
        self.assertEqual(result2, ["abc"])
        self.assertEqual(rest, "")

        result3, rest = first_of([parser1, parser2])(test_str2)
        self.assertIsNone(result3)
        self.assertEqual(rest, test_str2)

    def test_chain(self) -> None:
        test_str1 = "abc" + 3 * "def"
        test_str2 = "abc"
        parser = chain([begins_with("abc"), at_least_one(begins_with("def"))])

        result1, rest = parser(test_str1)
        self.assertEqual(result1, ["abc"] + 3 * ["def"])
        self.assertEqual(rest, "")

        result2, rest = parser(test_str2)
        self.assertIsNone(result2)
        self.assertEqual(rest, test_str2)


@pytest.mark.parametrize(
    "s, expected",
    [
        ("node003", (["node003"], "")),
        ("node060", (["node060"], "")),
        ("node100", (["node100"], "")),
        (
            "node[009-011,015]",
            (
                [
                    "node009",
                    "node010",
                    "node011",
                    "node015",
                ],
                "",
            ),
        ),
        # Test case for fair-sc cluster format
        (
            "h200-183-[001-003]",
            (
                [
                    "h200-183-001",
                    "h200-183-002",
                    "h200-183-003",
                ],
                "",
            ),
        ),
        # Test case for fair-sc cluster format with comma-separated values
        (
            "h100-193-[039,041,043]",
            (
                [
                    "h100-193-039",
                    "h100-193-041",
                    "h100-193-043",
                ],
                "",
            ),
        ),
        # Test case for multiple brackets in the nodelist
        (
            "node[1-2][3-4]",
            (
                [
                    "node13",
                    "node14",
                    "node23",
                    "node24",
                ],
                "",
            ),
        ),
        # Test case for multiple brackets with hyphens in the hostname
        (
            "h100-193-[001-002][3-4]",
            (
                [
                    "h100-193-0013",
                    "h100-193-0014",
                    "h100-193-0023",
                    "h100-193-0024",
                ],
                "",
            ),
        ),
        (
            "node[015-017,105-110]",
            (
                [
                    "node015",
                    "node016",
                    "node017",
                    "node105",
                    "node106",
                    "node107",
                    "node108",
                    "node109",
                    "node110",
                ],
                "",
            ),
        ),
        (
            "node[009-010,015,020,029,031,053,057,068,075,082,088,095,097-098,104]",
            (
                [
                    "node009",
                    "node010",
                    "node015",
                    "node020",
                    "node029",
                    "node031",
                    "node053",
                    "node057",
                    "node068",
                    "node075",
                    "node082",
                    "node088",
                    "node095",
                    "node097",
                    "node098",
                    "node104",
                ],
                "",
            ),
        ),
        ("node0003", (["node0003"], "")),
        ("node0060", (["node0060"], "")),
        ("node0100", (["node0100"], "")),
        ("node2021", (["node2021"], "")),
        (
            "node[0009-0011,0015]",
            (["node0009", "node0010", "node0011", "node0015"], ""),
        ),
        (
            "node[0015-0020,0105-0110]",
            (
                [
                    "node0015",
                    "node0016",
                    "node0017",
                    "node0018",
                    "node0019",
                    "node0020",
                    "node0105",
                    "node0106",
                    "node0107",
                    "node0108",
                    "node0109",
                    "node0110",
                ],
                "",
            ),
        ),
        (
            "node[0366,0427-0429,0431-0433,2010-2012,2043-2045,2057-2060,2062-2064]",
            (
                [
                    "node0366",
                    "node0427",
                    "node0428",
                    "node0429",
                    "node0431",
                    "node0432",
                    "node0433",
                    "node2010",
                    "node2011",
                    "node2012",
                    "node2043",
                    "node2044",
                    "node2045",
                    "node2057",
                    "node2058",
                    "node2059",
                    "node2060",
                    "node2062",
                    "node2063",
                    "node2064",
                ],
                "",
            ),
        ),
        (
            "h100-095-096,h100-105-164,h100-115-136,h100-138-083,h100-193-[043,073],h100-196-201,h100-228-185",
            (
                [
                    "h100-095-096",
                    "h100-105-164",
                    "h100-115-136",
                    "h100-138-083",
                    "h100-193-043",
                    "h100-193-073",
                    "h100-196-201",
                    "h100-228-185",
                ],
                "",
            ),
        ),
        ("node[100-102", (None, "node[100-102")),
        ("node100-102]", (None, "node100-102]")),
        ("", (None, "")),
    ],
)
@typechecked
def test_nodelist(s: str, expected: ParseResult[str]) -> None:
    p = nodelist()

    actual = p(s)

    assert actual == expected


@pytest.mark.parametrize(
    "e, expected",
    [
        ("1", (["1"], "")),
        ("", (None, "")),
        ("01", (["01"], "")),
        ("1-3", (["1", "2", "3"], "")),
        ("01-03", (["01", "02", "03"], "")),
        ("010-013", (["010", "011", "012", "013"], "")),
        ("1,2", (["1"], ",2")),
        ("1-3,4", (["1", "2", "3"], ",4")),
        ("1-3,5-7", (["1", "2", "3"], ",5-7")),
        (" 1", (None, " 1")),
        (" 1-3", (None, " 1-3")),
        ("[1-3", (None, "[1-3")),
    ],
)
@typechecked
def test_range_expression_element(e: str, expected: ParseResult[str]) -> None:
    p = range_expression_element()

    actual = p(e)

    assert actual == expected


@pytest.mark.parametrize(
    "e, expected",
    [
        ("[1,3]", (["1", "3"], "")),
        ("[1-3,5]", (["1", "2", "3", "5"], "")),
        ("[1-3,5-7]", (["1", "2", "3", "5", "6", "7"], "")),
        ("[01-03,5-7]", (["01", "02", "03", "5", "6", "7"], "")),
        ("[1]", (["1"], "")),
        ("[1,3]abc", (["1", "3"], "abc")),
    ],
)
@typechecked
def test_range_expression(e: str, expected: ParseResult[str]) -> None:
    p = range_expression()

    actual = p(e)

    assert actual == expected


@pytest.mark.parametrize(
    "e, expected",
    [
        (
            "a[0-2]-[3-5]",
            (
                [
                    "a0-3",
                    "a0-4",
                    "a0-5",
                    "a1-3",
                    "a1-4",
                    "a1-5",
                    "a2-3",
                    "a2-4",
                    "a2-5",
                ],
                "",
            ),
        ),
        (
            "a[0-2][3-5]",
            (
                [
                    "a03",
                    "a04",
                    "a05",
                    "a13",
                    "a14",
                    "a15",
                    "a23",
                    "a24",
                    "a25",
                ],
                "",
            ),
        ),
        (
            "node[009-011,015]",
            (
                [
                    "node009",
                    "node010",
                    "node011",
                    "node015",
                ],
                "",
            ),
        ),
        (
            "node[015-017,105-110]",
            (
                [
                    "node015",
                    "node016",
                    "node017",
                    "node105",
                    "node106",
                    "node107",
                    "node108",
                    "node109",
                    "node110",
                ],
                "",
            ),
        ),
        (
            "node[009-010,015,020,029,031,053,057,068,075,082,088,095,097-098,104]",
            (
                [
                    "node009",
                    "node010",
                    "node015",
                    "node020",
                    "node029",
                    "node031",
                    "node053",
                    "node057",
                    "node068",
                    "node075",
                    "node082",
                    "node088",
                    "node095",
                    "node097",
                    "node098",
                    "node104",
                ],
                "",
            ),
        ),
        ("node[009-011,015]abc", (None, "node[009-011,015]abc")),
        ("node[]", (None, "node[]")),
        ("node[009-011,015] ", (None, "node[009-011,015] ")),
    ],
)
@typechecked
def test_node_range_expression(e: str, expected: ParseResult[str]) -> None:
    p = node_range_expression()

    actual = p(e)

    assert actual == expected


class TestSLURMParsing:
    @staticmethod
    @pytest.mark.parametrize(
        "s, expected",
        [
            ("gpu:volta:8(S:0-1)", 8),
            ("gpu:pascal:2", 2),
            ("N/A", 0),
            ("gpu:8", 8),
            ("(null)", 0),
        ],
    )
    @typechecked
    def test_parse_gres(s: str, expected: int) -> None:
        actual = parse_gres(s)

        assert actual == expected

    @staticmethod
    @pytest.mark.parametrize(
        "s, expected_exc",
        [
            ("gpu:", ValueError),
            ("", ValueError),
            ("laser:1", ValueError),
            ("tpu:2", ValueError),
            # XXX: set test id manually because the default one derived from the param
            # value messes up tpx
            pytest.param("gpu::8", ValueError, id="double colon"),
        ],
    )
    @typechecked
    def test_parse_gres_throws(s: str, expected_exc: Type[BaseException]) -> None:
        with pytest.raises(expected_exc):
            parse_gres(s)

    @staticmethod
    @pytest.mark.parametrize("s, expected", [("gpu:2", 2), ("gpu:8", 8), ("N/A", 0)])
    @typechecked
    def test_parse_tres(s: str, expected: int) -> None:
        actual = parse_tres(s)

        assert actual == expected

    @staticmethod
    @pytest.mark.parametrize(
        "s, expected_exc", [("hello", ValueError), ("gpu:", ValueError)]
    )
    @typechecked
    def test_parse_tres_throws(s: str, expected_exc: Type[BaseException]) -> None:
        with pytest.raises(expected_exc):
            parse_tres(s)


@pytest.mark.parametrize(
    "s, expected", [("gres/gpu=8", 8), ("tres1=1,gres/gpu=2,tres3=4", 2), ("", 0)]
)
def test_parse_gpu_from_tres(s: str, expected: int) -> None:
    assert parse_value_from_tres(s, "gres/gpu") == expected


@pytest.mark.parametrize("s, exc", [("not_a_tres_string", ValueError)])
def test_parse_gpu_from_tres_bad(s: str, exc: Type[Exception]) -> None:
    with pytest.raises(exc):
        parse_value_from_tres(s, "gres/gpu")


if __name__ == "__main__":
    unittest.main()
