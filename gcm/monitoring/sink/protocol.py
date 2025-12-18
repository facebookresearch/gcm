# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from enum import auto, Enum
from typing import Optional, Protocol, runtime_checkable, TypeVar

from gcm.schemas.log import Log


TIn_contra = TypeVar("TIn_contra", contravariant=True)


class DataType(Enum):
    LOG = auto()
    METRIC = auto()


class DataIdentifier(Enum):
    JOB = auto()
    NODE = auto()
    STATVFS = auto()
    PURE = auto()
    GENERIC = auto()


@dataclass
class SinkAdditionalParams:
    """Sinks may use this information as needed, useful to send collection specific data."""

    data_type: Optional[DataType] = None
    data_identifier: Optional[DataIdentifier] = None
    heterogeneous_cluster_v1: bool = False


class Sink(Protocol[TIn_contra]):
    """A destination for data to go."""

    def write(self, data: TIn_contra) -> None:
        """Put the data somewhere."""


class SinkWrite(Protocol):
    def __call__(self, data: Log, additional_params: SinkAdditionalParams) -> None: ...


@runtime_checkable
class SinkImpl(Protocol):
    """A destination for data."""

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        """Writes data to the specified sink, see available sinks in /exporters."""
