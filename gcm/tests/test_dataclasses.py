# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, TYPE_CHECKING

import pytest

from gcm.monitoring.dataclass_utils import flatten_dict_factory, Flattened, max_fields
from gcm.monitoring.meta_utils.scuba import ScubaMessage, to_scuba_message
from pydantic import BaseModel
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass
class M:
    x: int
    y: float
    z: Optional[int]


@dataclass
class MM(M):
    a: str


@dataclass
class ValidDict:
    a: Dict[str, str | float | int]


@dataclass
class InvalidDict:
    a: Dict[str | int, str]


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (M(x=-3, y=5.0, z=1), M(x=2, y=1.5, z=-2), M(x=2, y=5.0, z=1)),
        (M(x=-3, y=5.0, z=None), M(x=2, y=1.5, z=-2), M(x=2, y=5.0, z=-2)),
        (M(x=-3, y=5.0, z=1), M(x=2, y=1.5, z=None), M(x=2, y=5.0, z=1)),
        (M(x=-3, y=5.0, z=None), M(x=2, y=1.5, z=None), M(x=2, y=5.0, z=None)),
        (M(x=-3, y=5.0, z=1), MM(x=2, y=1.5, z=-2, a="hello"), M(x=2, y=5.0, z=1)),
        (MM(x=2, y=1.5, z=-2, a="hello"), M(x=-3, y=5.0, z=1), M(x=2, y=5.0, z=1)),
    ],
)
@typechecked
def test_max_fields(a: M, b: M, expected: M) -> None:
    op = max_fields(M)

    actual = op(a, b)

    assert actual == expected


def test_max_fields_op_throws_on_invalid_inputs() -> None:
    @dataclass
    class NotM:
        x: int = 0

    op = max_fields(M)

    with pytest.raises(TypeError):
        op(M(x=0, y=1.0, z=None), NotM())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        op(NotM(), M(x=0, y=1.0, z=None))  # type: ignore[arg-type]


def test_max_fields_op_throws_on_incomparable_fields() -> None:
    class Foo:
        pass

    @dataclass
    class HasIncomparable:
        f: Foo = field(default_factory=Foo)
        x: int = 0

    op = max_fields(HasIncomparable)

    with pytest.raises(TypeError):
        op(HasIncomparable(), HasIncomparable())


@pytest.mark.parametrize(
    "dc, expected",
    [
        (
            MM(x=4, y=3.0, z=-1, a="hello"),
            ScubaMessage(
                int={"x": 4, "z": -1}, double={"y": 3.0}, normal={"a": "hello"}
            ),
        ),
        (
            MM(x=4, y=3.0, z=None, a="hello"),
            ScubaMessage(int={"x": 4}, double={"y": 3.0}, normal={"a": "hello"}),
        ),
        (
            ValidDict(a={"x": 4, "y": 3.0, "a": "hello"}),
            ScubaMessage(int={"a.x": 4}, double={"a.y": 3.0}, normal={"a.a": "hello"}),
        ),
    ],
)
def test_to_scuba_message(dc: MM, expected: ScubaMessage) -> None:
    actual = to_scuba_message(dc)

    assert actual == expected


def test_to_scuba_message_throws_on_dict_non_string_keys() -> None:
    with pytest.raises(TypeError):
        to_scuba_message(InvalidDict({1: "val", "1": "val2"}))


def test_to_scuba_message_throws_on_uninferrable_type() -> None:
    class Foo:
        pass

    @dataclass
    class HasUninferrableType:
        f: Foo = field(default_factory=Foo)
        x: int = 0

    with pytest.raises(TypeError):
        to_scuba_message(HasUninferrableType())


@dataclass
class TestBaseTypes:
    __test__ = False
    a: int
    b: str
    c: bool
    d: float
    e: Optional[str]


@dataclass
class TestList:
    __test__ = False
    a: list[str]


@dataclass
class HelperDataclass:
    hd_a: str


@dataclass
class NamedHelperDataclass:
    name: str
    nhd_a: str


@dataclass
class TestDataclass:
    __test__ = False
    a: HelperDataclass
    b: NamedHelperDataclass


class TestPydantic(BaseModel):
    __test__ = False
    name: str
    a: str
    b: int


class TestPydanticList(BaseModel):
    __test__ = False
    a: list[TestPydantic]


@dataclass
class TestNestedPydantic:
    __test__ = False
    pydantic_obj: TestPydantic
    pydantic_list: list[TestPydantic]
    pydantic_nested_list: list[TestPydanticList]


@dataclass
class TestDict:
    __test__ = False
    a: dict[str, str]
    b: dict[str, list[str]]
    c: dict[str, dict[str, str]]
    d: dict[int, str]
    e: dict[str, dict[int, str]]


@dataclass
class TestNestedList:
    __test__ = False
    a: list[list[str]]


@dataclass
class TestNestedDictList:
    __test__ = False
    nested_base: list[dict[str, str | int | TestNestedList]]
    nested_dict: list[dict[str, TestDict]]
    nested_list: list[dict[str, TestNestedList]]
    nested_pydantic: list[dict[str, str | TestPydantic]]


@pytest.mark.parametrize(
    "data, expected",
    [
        (
            TestBaseTypes(a=1, b="a", c=True, d=1.10, e=None),
            {"a": 1, "b": "a", "c": True, "d": 1.10},
        ),
        (
            TestBaseTypes(a=1, b="a", c=True, d=1.10, e="a"),
            {"a": 1, "b": "a", "c": True, "d": 1.10, "e": "a"},
        ),
        (TestList(a=[]), {}),
        (TestList(a=[""]), {"a.0": ""}),
        (TestList(a=["1", "2"]), {"a.0": "1", "a.1": "2"}),
        (
            TestDataclass(
                a=HelperDataclass(hd_a="abc"),
                b=NamedHelperDataclass(name="test_name", nhd_a="def"),
            ),
            {"a.hd_a": "abc", "b.test_name.nhd_a": "def"},
        ),
        (
            TestNestedPydantic(
                pydantic_obj=TestPydantic(name="test_obj", a="1", b=2),
                pydantic_list=[
                    TestPydantic(name="test_list_obj1", a="1", b=2),
                    TestPydantic(name="test_list_obj2", a="3", b=4),
                ],
                pydantic_nested_list=[
                    TestPydanticList(
                        a=[
                            TestPydantic(name="abc", a="1", b=2),
                            TestPydantic(name="def", a="3", b=4),
                        ]
                    ),
                    TestPydanticList(
                        a=[
                            TestPydantic(name="ghi", a="5", b=6),
                            TestPydantic(name="jkl", a="7", b=8),
                        ]
                    ),
                ],
            ),
            {
                "pydantic_obj.test_obj.a": "1",
                "pydantic_obj.test_obj.b": 2,
                "pydantic_list.test_list_obj1.a": "1",
                "pydantic_list.test_list_obj1.b": 2,
                "pydantic_list.test_list_obj2.a": "3",
                "pydantic_list.test_list_obj2.b": 4,
                "pydantic_nested_list.0.a.abc.a": "1",
                "pydantic_nested_list.0.a.abc.b": 2,
                "pydantic_nested_list.0.a.def.a": "3",
                "pydantic_nested_list.0.a.def.b": 4,
                "pydantic_nested_list.1.a.ghi.a": "5",
                "pydantic_nested_list.1.a.ghi.b": 6,
                "pydantic_nested_list.1.a.jkl.a": "7",
                "pydantic_nested_list.1.a.jkl.b": 8,
            },
        ),
        (
            TestDict(
                a={"key1": "1"},
                b={"key2": ["i1", "i2"]},
                c={"key3": {"key4": "2"}},
                d={},
                e={},
            ),
            {"a.key1": "1", "b.key2.0": "i1", "b.key2.1": "i2", "c.key3.key4": "2"},
        ),
        (
            TestDict(
                a={"key1": "1"},
                b={"key2": ["i1", "i2"]},
                c={"key3": {"key4": "2"}},
                d={0: "foo"},
                e={},
            ),
            {
                "a.key1": "1",
                "b.key2.0": "i1",
                "b.key2.1": "i2",
                "c.key3.key4": "2",
                "d.0": "foo",
            },
        ),
        (
            TestDict(
                a={"key1": "1"},
                b={"key2": ["i1", "i2"]},
                c={"key3": {"key4": "2"}},
                d={0: "foo"},
                e={"": {0: "foo"}},
            ),
            {
                "a.key1": "1",
                "b.key2.0": "i1",
                "b.key2.1": "i2",
                "c.key3.key4": "2",
                "d.0": "foo",
                "e..0": "foo",
            },
        ),
        (TestNestedList(a=[[]]), {}),
        (TestNestedList(a=[["i1"]]), {"a.0.0": "i1"}),
        (
            TestNestedDictList(
                nested_base=[], nested_dict=[], nested_list=[], nested_pydantic=[]
            ),
            {},
        ),
        (
            TestNestedDictList(
                nested_base=[{}], nested_dict=[], nested_list=[], nested_pydantic=[]
            ),
            {},
        ),
        (
            TestNestedDictList(
                nested_base=[{"key1": 1}],
                nested_dict=[],
                nested_list=[],
                nested_pydantic=[],
            ),
            {"nested_base.0.key1": 1},
        ),
        (
            TestNestedDictList(
                nested_base=[{"name": "nested_dict_list", "key1": 1}],
                nested_dict=[],
                nested_list=[],
                nested_pydantic=[],
            ),
            {"nested_base.nested_dict_list.key1": 1},
        ),
        (
            TestNestedDictList(
                nested_base=[
                    {"name": "nested_dict_list", "key1": TestNestedList(a=[["i1"]])}
                ],
                nested_dict=[],
                nested_list=[{"key1": TestNestedList(a=[["i1"]])}],
                nested_pydantic=[],
            ),
            {
                "nested_base.nested_dict_list.key1.a.0.0": "i1",
                "nested_list.0.key1.a.0.0": "i1",
            },
        ),
        (
            TestNestedDictList(
                nested_base=[
                    {"name": "nested_dict_list", "key1": TestNestedList(a=[["i1"]])}
                ],
                nested_dict=[
                    {
                        "key1": TestDict(
                            a={"key1": "1"},
                            b={"key2": ["i1", "i2"]},
                            c={"key3": {"key4": "2"}},
                            d={},
                            e={},
                        )
                    }
                ],
                nested_list=[{"key1": TestNestedList(a=[["i1"]])}],
                nested_pydantic=[],
            ),
            {
                "nested_base.nested_dict_list.key1.a.0.0": "i1",
                "nested_list.0.key1.a.0.0": "i1",
                "nested_dict.0.key1.a.key1": "1",
                "nested_dict.0.key1.b.key2.0": "i1",
                "nested_dict.0.key1.b.key2.1": "i2",
                "nested_dict.0.key1.c.key3.key4": "2",
            },
        ),
        (
            TestNestedDictList(
                nested_base=[
                    {"name": "nested_dict_list", "key1": TestNestedList(a=[["i1"]])}
                ],
                nested_dict=[
                    {
                        "key1": TestDict(
                            a={"key1": "1"},
                            b={"key2": ["i1", "i2"]},
                            c={"key3": {"key4": "2"}},
                            d={},
                            e={},
                        )
                    }
                ],
                nested_list=[{"key1": TestNestedList(a=[["i1"]])}],
                nested_pydantic=[
                    {
                        "name": "named_pydantic",
                        "key1": TestPydantic(name="abc", a="1", b=2),
                    }
                ],
            ),
            {
                "nested_base.nested_dict_list.key1.a.0.0": "i1",
                "nested_list.0.key1.a.0.0": "i1",
                "nested_dict.0.key1.a.key1": "1",
                "nested_dict.0.key1.b.key2.0": "i1",
                "nested_dict.0.key1.b.key2.1": "i2",
                "nested_dict.0.key1.c.key3.key4": "2",
                "nested_pydantic.named_pydantic.key1.abc.a": "1",
                "nested_pydantic.named_pydantic.key1.abc.b": 2,
            },
        ),
    ],
)
def test_asdict_recursive(data: DataclassInstance, expected: Flattened) -> None:
    actual = asdict(data, dict_factory=flatten_dict_factory)
    assert actual == expected
