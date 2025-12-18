# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Collection, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

logger = logging.getLogger(__name__)


@dataclass
class ScubaMessage:
    _int = int
    int: Dict[str, _int] = field(default_factory=dict)  # type: ignore[valid-type]
    double: Dict[str, float] = field(default_factory=dict)
    normal: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, Collection[str]] = field(default_factory=dict)


def to_scuba_message(dc: DataclassInstance) -> ScubaMessage:
    """Attempt to convert a dataclass to a Scuba message."""
    if not is_dataclass(dc):
        raise TypeError(f"{type(dc).__name__} is not a dataclass.")

    if isinstance(dc, ScubaMessage):
        return dc

    scuba_message = ScubaMessage()

    def insert_scuba_field(name: str, value: Any) -> None:
        if value is None:
            return

        ty = type(value)

        if isinstance(ty, type):
            if issubclass(ty, dict):
                for key in value:
                    if not isinstance(key, str):
                        raise TypeError(
                            "All dictionary keys should be string to avoid naming collision"
                        )
                    nested_value = value[key]
                    insert_scuba_field(f"{name}.{key}", nested_value)
                return

            # e.g. 'int' or user-defined class
            if issubclass(ty, str):
                scuba_message.normal[name] = value
                return

            try:
                as_list = list(value)
            except TypeError:
                pass
            else:
                scuba_message.tags[name] = as_list
                return

            if issubclass(ty, int):
                scuba_message.int[name] = value
                return

            if issubclass(ty, float):
                scuba_message.double[name] = value
                return

            raise TypeError(
                f"Could not infer Scuba type from type '{ty.__name__}' for field '{name}'."
            )

        raise TypeError(f"Could not infer Scuba type from type '{ty.__name__}'")

    for f in fields(dc):
        insert_scuba_field(f.name, getattr(dc, f.name))

    return scuba_message
