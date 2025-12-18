# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging

from dataclasses import fields, is_dataclass
from typing import Any, Callable, cast, Hashable, Mapping, Type, TypeVar

from pydantic import BaseModel

from typeguard import typechecked

logger = logging.getLogger(__name__)


_TDataclass = TypeVar("_TDataclass")
BaseType = int | float | str | bool
NonFlattened = object
FlattenedOrBaseType = dict[str, BaseType] | BaseType
Flattened = dict[str, BaseType]


def instantiate_dataclass(
    cls: Type[_TDataclass], data: Mapping[Hashable, Any], logger: logging.Logger
) -> _TDataclass:
    if not is_dataclass(cls):
        raise TypeError(f"{type(cls).__name__} is not a dataclass.")
    parsed_data = {}
    for field in fields(cls):
        field_name = field.metadata.get("field_name", field.name)
        class_name = field.name
        if field_name in data:
            value = data[field_name]
            parser = field.metadata.get("parser", lambda value: value)
            parsed_data[class_name] = parser(value)
        else:
            logger.warning(f"Missing {field_name=} when instantiating {cls.__name__=}")
            parsed_data[class_name] = None
    return cast(_TDataclass, cls(**parsed_data))


def asdict_recursive(obj: NonFlattened, key: str = "") -> FlattenedOrBaseType:
    # somewhat inspired by _asdict_inner https://github.com/python/cpython/blob/3.13/Lib/dataclasses.py#L1362
    results = {}
    if is_dataclass(obj):
        if hasattr(obj, "name") and (name := getattr(obj, "name")):
            key += "." + name
        for field in fields(obj):
            if field.name == "name":
                continue
            value = getattr(obj, field.name)
            if value is None:
                continue
            flat_result = asdict_recursive(value, key)
            if isinstance(flat_result, dict):
                results.update(flat_result)
            else:
                results[key] = flat_result
    elif isinstance(obj, BaseModel):
        dumped_value = obj.model_dump(exclude={"name"})
        if hasattr(obj, "name") and (name := getattr(obj, "name")):
            key += "." + name
        flat_result = asdict_recursive(dumped_value, key)
        if isinstance(flat_result, dict):
            results.update(flat_result)
        else:
            results[key] = flat_result
    elif isinstance(obj, dict):
        if "name" in obj:
            key += "." + str(obj["name"])
            del obj["name"]
        for k, value in obj.items():
            if value is None:
                continue
            new_key = f"{key}.{k}" if key else str(k)
            flat_result = asdict_recursive(value, new_key)
            if isinstance(flat_result, dict):
                results.update(flat_result)
            else:
                results[new_key] = flat_result
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if value is None:
                continue
            if hasattr(value, "name") or (isinstance(value, dict) and "name" in value):
                new_key = key
            else:
                new_key = key + f".{i}"
            flat_result = asdict_recursive(value, new_key)
            if isinstance(flat_result, dict):
                results.update(flat_result)
            else:
                results[new_key] = flat_result
    elif isinstance(obj, tuple):
        # TODO: add support for tuples
        raise TypeError("Tuples are not supported for asdict_recursive.")
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    else:
        raise TypeError(f"{type(obj)} is not supported for asdict_recursive.")
    return results


def flatten_dict_factory(pairs: list[tuple[str, object | BaseModel]]) -> Flattened:
    """
    Custom dict factory to be passed to dataclasses's asdict https://docs.python.org/3/library/dataclasses.html#dataclasses.asdict

    Things that are special about this dict_factory:
        1. It flattens a dictionary with . separated naming at the top level.
            this:
            {
                obj1: {
                    a: 1,
                    b: 2,
                }
            }
            becomes:
            {"obj1.a" = 1, "obj1.b": 2}

        2. It flattens lists with . separated list indexes (unless the list object matches rule 3)
            this:
            {
                obj1: ['a', 'b']
            }
            becomes:
            {"obj1.0" = 'a', "obj1.1": 'b'}

        3. It flattens {pydantic's Base Models, Dict, and Dataclasses} taking `name` field (if present) as one of the `.` separated keys for the flattened dictionary, if name is available list objects won't have the index:
            this:
            class Test(BaseModel):
                name: str
                obj: int
            {
                obj1: Test(name="TestModelName", test_obj=123)
            }
            becomes:
            {"obj1.TestModelName.test_obj" = 123}
    """
    results = {}
    for key, value in pairs:
        if value is None:
            continue
        flat_result = asdict_recursive(value, key)
        if isinstance(flat_result, dict):
            results.update(flat_result)
        else:
            results[key] = flat_result
    return results


def remove_none_dict_factory(
    pairs: list[tuple[str, object | BaseModel]],
) -> dict[str, object]:
    return {key: value for key, value in pairs if value is not None}


@typechecked
def max_fields(
    cls: Type[_TDataclass],
) -> Callable[[_TDataclass, _TDataclass], _TDataclass]:
    """Construct an operator for a dataclass which is defined by
        max_fields(cls)(a, b).f := max'(a.f, b.f)
    for all dataclasses `cls` and instances `a` and `b`, where max' is an extension of
    `max` defined by
        max'(x, None) := x
        max'(None, y) := y
        max'(x, y)    := max(x, y)
    """
    if not is_dataclass(cls):
        raise TypeError(f"{type(cls).__name__} is not a dataclass.")

    def op(left: _TDataclass, right: _TDataclass) -> _TDataclass:
        if not isinstance(left, cls):
            raise TypeError(
                f"Expected '{cls.__name__}' but got {type(left).__name__} for left argument."
            )
        if not isinstance(right, cls):
            raise TypeError(
                f"Expected '{cls.__name__}' but got {type(right).__name__} for right argument."
            )

        kwargs = {}
        for name in (f.name for f in fields(cls)):
            left_value = getattr(left, name)
            right_value = getattr(right, name)
            if left_value is None:
                kwargs[name] = right_value
            elif right_value is None:
                kwargs[name] = left_value
            else:
                kwargs[name] = max(left_value, right_value)
        return cast(_TDataclass, cls(**kwargs))

    return op
