# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from enum import Enum
from typing import Literal, Protocol

CHECK_TYPE = Literal["prolog", "epilog", "nagios", "app"]
LOG_LEVEL = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class CheckEnv(Protocol):
    @property
    def cluster(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def log_level(self) -> str: ...

    @property
    def log_folder(self) -> str: ...


class ExitCode(Enum):
    """The exit code values were selected to be in sync with the Nagios documentation https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html"""

    OK = 0
    WARN = 1
    CRITICAL = 2
    UNKNOWN = 3  # Unknown will have a lower precedance than the rest of the ExitCodes for comparison purposes.

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ExitCode) and self.value == other.value

    def __le__(self, other: object) -> bool:
        if self == ExitCode.UNKNOWN:
            return True
        elif isinstance(other, ExitCode) and other == ExitCode.UNKNOWN:
            return False
        else:
            return isinstance(other, ExitCode) and self.value <= other.value

    def __ge__(self, other: object) -> bool:
        if self == ExitCode.UNKNOWN:
            return False
        elif isinstance(other, ExitCode) and other == ExitCode.UNKNOWN:
            return True
        else:
            return isinstance(other, ExitCode) and self.value >= other.value

    def __hash__(self) -> int:
        """Make this class hashable."""
        return hash(self.value)

    def __lt__(self, other: object) -> bool:
        if self == ExitCode.UNKNOWN:
            return True
        elif isinstance(other, ExitCode) and other == ExitCode.UNKNOWN:
            return False
        else:
            return isinstance(other, ExitCode) and self.value < other.value

    def __gt__(self, other: object) -> bool:
        if self == ExitCode.UNKNOWN:
            return False
        elif isinstance(other, ExitCode) and other == ExitCode.UNKNOWN:
            return True
        else:
            return isinstance(other, ExitCode) and self.value > other.value
