# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import field
from typing import Callable, cast, Optional, TypeVar


T = TypeVar("T")


def parsed_field(
    parser: Callable[[str], T],
    field_name: Optional[str] = None,
    slurm_field: bool = True,
) -> T:
    """
    Arguments:
        parser (Callable): Function responsible for parsing slurm cli output field into their expected shape.
        field_name (str): Str definition used as the field_name when interacting with slurm cli.
        slurm_field (bool): Boolean used to mark if the field is expected to come from querying slurm.
    """
    metadata: dict[str, Callable[[str], T] | str | bool] = {
        "parser": parser,
        "slurm_field": slurm_field,
    }
    if field_name is not None:
        metadata["field_name"] = field_name
    return cast(T, field(metadata=metadata))
