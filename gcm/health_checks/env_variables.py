# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
from types import TracebackType
from typing import Dict, Optional, Type


class EnvCtx:
    """Stores the environment variables passed as a dictionary and on exit it restores the variables that have a value."""

    env_variables: Dict[str, Optional[str]]
    original_env_variables: Dict[str, Optional[str]]

    def __init__(self, env_dict: Dict[str, Optional[str]]) -> None:
        self.env_variables = env_dict
        self.original_env_variables = {}

    def __enter__(self) -> None:
        for variable, value in self.env_variables.items():
            self.original_env_variables[variable] = os.getenv(variable)
            if value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = value

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        exc_traceback: Optional[TracebackType],
    ) -> None:
        for variable, value in self.original_env_variables.items():
            if value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = value

        for variable in self.env_variables:
            if variable not in self.original_env_variables:
                os.environ.pop(variable, None)
