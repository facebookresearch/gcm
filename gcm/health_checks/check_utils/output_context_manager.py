# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import types
from dataclasses import dataclass
from typing import Callable, ContextManager, Literal, NoReturn, Optional, Tuple, Type

from gcm.health_checks.types import CHECK_TYPE, ExitCode

from gcm.schemas.health_check.health_check_name import HealthCheckName


def assert_never(exit_code: NoReturn) -> NoReturn:
    assert False, f"Undefined exit_code was received: {exit_code}"


@dataclass
class OutputContext(ContextManager["OutputContext"]):
    type: CHECK_TYPE
    name: HealthCheckName
    get_exit_code_msg: Callable[[], Tuple[ExitCode, str]]
    verbose_out: bool

    def __enter__(self) -> "OutputContext":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> Literal[False]:
        if exc_type != SystemExit and exc_type is not None:
            print("WARNING - check did not exit normally")
            return False

        output_msg = ""
        exit_code, msg = self.get_exit_code_msg()
        if self.verbose_out or self.type == "nagios" or self.type == "app":
            if exit_code is ExitCode.OK:
                output_msg += "OK - "
            elif exit_code is ExitCode.WARN:
                output_msg += "WARNING - "
            elif exit_code is ExitCode.CRITICAL:
                output_msg += "CRITICAL - "
            elif exit_code is ExitCode.UNKNOWN:
                output_msg += "UNKNOWN - "
            else:
                assert_never(exit_code)
            output_msg += self.name.value
            if self.verbose_out or self.type == "app":
                if msg != "":
                    output_msg += ". " + msg
            print(output_msg)

        return False
