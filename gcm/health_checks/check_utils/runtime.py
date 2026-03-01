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
from typing import Callable, ContextManager, Literal, NoReturn, Optional, Type

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName


@dataclass
class HealthCheckRuntime(ContextManager["HealthCheckRuntime"]):
    cluster: str
    type: CHECK_TYPE
    log_level: LOG_LEVEL
    log_folder: str
    sink: str
    sink_opts: Collection[str]
    verbose_out: bool
    heterogeneous_cluster_v1: bool
    health_check_name: HealthCheckName
    killswitch_getter: Callable[[], bool]

    logger: logging.Logger = field(init=False)
    node: str = field(init=False)
    gpu_node_id: Optional[str] = field(init=False)
    derived_cluster: str = field(init=False)
    exit_code: ExitCode = field(init=False, default=ExitCode.UNKNOWN)
    msg: str = field(init=False, default="")
    _stack: ExitStack = field(init=False)

    def __enter__(self) -> "HealthCheckRuntime":
        self.node = socket.gethostname()
        self.logger, _ = init_logger(
            logger_name=self.type,
            log_dir=str(Path(self.log_folder) / self.type / "_logs"),
            log_name=self.node + ".log",
            log_level=getattr(logging, self.log_level),
        )
        self.logger.info(
            "%s: cluster: %s, node: %s, type: %s",
            self.health_check_name.value,
            self.cluster,
            self.node,
            self.type,
        )
        try:
            self.gpu_node_id = gni_lib.get_gpu_node_id()
        except Exception as e:
            self.gpu_node_id = None
            self.logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")

        self.derived_cluster = get_derived_cluster(
            cluster=self.cluster,
            heterogeneous_cluster_v1=self.heterogeneous_cluster_v1,
            data={"Node": self.node},
        )

        self._stack = ExitStack()
        self._stack.__enter__()
        self._stack.enter_context(
            TelemetryContext(
                sink=self.sink,
                sink_opts=self.sink_opts,
                logger=self.logger,
                cluster=self.cluster,
                derived_cluster=self.derived_cluster,
                type=self.type,
                name=self.health_check_name.value,
                node=self.node,
                get_exit_code_msg=lambda: (self.exit_code, self.msg),
                gpu_node_id=self.gpu_node_id,
            )
        )
        self._stack.enter_context(
            OutputContext(
                self.type,
                self.health_check_name,
                lambda: (self.exit_code, self.msg),
                self.verbose_out,
            )
        )

        if self.killswitch_getter():
            self.exit_code = ExitCode.OK
            self.logger.info(
                "%s is disabled by killswitch",
                self.health_check_name.value,
            )
            sys.exit(0)

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
        self.exit_code = exit_code
        self.msg = msg
        sys.exit(exit_code.value)
