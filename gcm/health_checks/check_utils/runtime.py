# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import socket
import sys
import types
from collections.abc import Collection
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ContextManager, Literal, NoReturn, Optional, Tuple, Type

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName


def _default_get_hostname() -> str:
    return socket.gethostname()


def _default_get_gpu_node_id() -> Optional[str]:
    return gni_lib.get_gpu_node_id()


def _default_init_logger(
    logger_name: str, log_dir: str, log_name: str, log_level: int
) -> Tuple[logging.Logger, logging.Handler]:
    return init_logger(
        logger_name=logger_name,
        log_dir=log_dir,
        log_name=log_name,
        log_level=log_level,
    )


def _default_get_derived_cluster(
    cluster: str, heterogeneous_cluster_v1: bool, data: dict
) -> str:
    return get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data=data,
    )


@dataclass
class HealthCheckRuntime(ContextManager["HealthCheckRuntime"]):
    """Context manager encapsulating shared health check setup and teardown.

    Handles logger initialization, GPU node ID detection, derived cluster
    resolution, TelemetryContext/OutputContext lifecycle, and killswitch
    checking. Use ``finish()`` to set the final exit code and terminate.
    """

    cluster: str
    check_type: CHECK_TYPE
    log_level: LOG_LEVEL
    log_folder: str
    sink: str
    sink_opts: Collection[str]
    verbose_out: bool
    heterogeneous_cluster_v1: bool
    health_check_name: HealthCheckName
    killswitch_getter: Callable[[], bool]

    # Injectable dependencies for testing.
    get_hostname: Callable[[], str] = _default_get_hostname
    get_gpu_node_id: Callable[[], Optional[str]] = _default_get_gpu_node_id
    init_logger: Callable[
        [str, str, str, int], Tuple[logging.Logger, logging.Handler]
    ] = _default_init_logger
    get_derived_cluster: Callable[[str, bool, dict], str] = _default_get_derived_cluster
    telemetry_context_factory: Callable[..., ContextManager] = TelemetryContext
    output_context_factory: Callable[..., ContextManager] = OutputContext

    logger: logging.Logger = field(init=False)
    node: str = field(init=False)
    gpu_node_id: Optional[str] = field(init=False)
    derived_cluster: str = field(init=False)
    exit_code: ExitCode = field(init=False, default=ExitCode.UNKNOWN)
    msg: str = field(init=False, default="")
    _stack: ExitStack = field(init=False)

    def __enter__(self) -> "HealthCheckRuntime":
        self.node = self.get_hostname()
        self.logger, _ = self.init_logger(
            self.check_type,
            str(Path(self.log_folder) / (self.check_type + "_logs")),
            self.node + ".log",
            getattr(logging, self.log_level),
        )
        self.logger.info(
            "%s: cluster: %s, node: %s, type: %s",
            self.health_check_name.value,
            self.cluster,
            self.node,
            self.check_type,
        )
        try:
            self.gpu_node_id = self.get_gpu_node_id()
        except Exception as e:
            self.gpu_node_id = None
            self.logger.warning(
                "Could not get gpu_node_id, likely not a GPU host: %s", e
            )

        self.derived_cluster = self.get_derived_cluster(
            self.cluster,
            self.heterogeneous_cluster_v1,
            {"Node": self.node},
        )

        # Manage ExitStack manually so it spans both __enter__ and __exit__.
        self._stack = ExitStack()
        self._stack.__enter__()
        self._stack.enter_context(
            self.telemetry_context_factory(
                sink=self.sink,
                sink_opts=self.sink_opts,
                logger=self.logger,
                cluster=self.cluster,
                derived_cluster=self.derived_cluster,
                type=self.check_type,
                name=self.health_check_name.value,
                node=self.node,
                get_exit_code_msg=lambda: (self.exit_code, self.msg),
                gpu_node_id=self.gpu_node_id,
            )
        )
        self._stack.enter_context(
            self.output_context_factory(
                self.check_type,
                self.health_check_name,
                lambda: (self.exit_code, self.msg),
                self.verbose_out,
            )
        )

        if self.killswitch_getter():
            self.exit_code = ExitCode.OK
            self.msg = f"{self.health_check_name.value} is disabled by killswitch."
            self.logger.info(self.msg)
            # Properly clean contexts before exit since __exit__ is not
            # called when SystemExit is raised inside __enter__.
            self._stack.__exit__(None, None, None)
            sys.exit(self.exit_code.value)

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> Literal[False]:
        self._stack.__exit__(exc_type, exc_val, exc_tb)
        return False

    def finish(self, exit_code: ExitCode, msg: str) -> NoReturn:
        """Set the final exit code and message, then terminate via ``sys.exit``."""
        self.exit_code = exit_code
        self.msg = msg
        sys.exit(exit_code.value)
