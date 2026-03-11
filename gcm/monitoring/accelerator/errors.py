# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.monitoring.accelerator.backend import BackendName


class AcceleratorError(Exception):
    """Base exception type for accelerator HAL failures."""


class BackendUnavailableError(AcceleratorError):
    """Raised when backend probe fails due to missing runtime dependencies."""


class UnsupportedOperationError(AcceleratorError):
    """Raised when an operation is not implemented by a backend."""


@dataclass(frozen=True)
class BackendOperationError(AcceleratorError):
    backend: BackendName
    operation: str

    def __str__(self) -> str:
        return f"backend={self.backend.value} operation={self.operation}"
