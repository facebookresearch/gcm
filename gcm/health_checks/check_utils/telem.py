# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import time
import types
from dataclasses import dataclass, field
from typing import (
    Callable,
    Collection,
    ContextManager,
    Dict,
    Literal,
    Optional,
    Tuple,
    Type,
)

from gcm.exporters import registry
from gcm.health_checks.types import CHECK_TYPE, ExitCode

from gcm.monitoring.clock import ClockImpl
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.schemas.health_check.log import HealthCheckLog
from gcm.schemas.log import Log
from omegaconf import OmegaConf as oc


def get_telemetry_record(
    cluster: str,
    derived_cluster: str,
    type: str,
    health_check: str,
    node: str,
    gpu_node_id: Optional[str],
    exit_code: ExitCode,
    msg: str = "",
    start_time: float = 0.0,
    end_time: float = 0.0,
    job_id: int = 0,
) -> HealthCheckLog:
    return HealthCheckLog(
        node=node,
        gpu_node_id=gpu_node_id,
        cluster=cluster,
        derived_cluster=derived_cluster,
        health_check=health_check,
        type=type,
        result=exit_code.value,
        _msg=msg,
        job_id=job_id,
        start_time=start_time,
        end_time=end_time,
    )


@dataclass
class TelemetryContext(ContextManager["TelemetryContext"]):
    sink: str
    sink_opts: Collection[str]
    logger: logging.Logger
    cluster: str
    derived_cluster: str
    type: CHECK_TYPE
    name: str
    node: str
    get_exit_code_msg: Callable[[], Tuple[ExitCode, str]]
    gpu_node_id: Optional[str]
    job_id: Optional[int] = None
    telem_registry: Dict[str, Factory[SinkImpl]] = field(
        default_factory=lambda: registry
    )

    def __enter__(self) -> "TelemetryContext":
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> Literal[False]:
        self.end_time = time.time()
        exit_code, msg = self.get_exit_code_msg()
        if self.job_id is None:
            self.job_id = 0
            if self.type in ["prolog", "epilog"]:
                if "SLURM_JOB_ID" in os.environ:
                    self.job_id = int(os.environ["SLURM_JOB_ID"])
                else:
                    self.logger.error(
                        "SLURM_JOB_ID is not set for prolog/epilog check."
                    )
                    msg = msg + "\nSLURM_JOB_ID is not set for prolog/epilog check."

        record = get_telemetry_record(
            cluster=self.cluster,
            derived_cluster=self.derived_cluster,
            type=self.type,
            health_check=self.name,
            node=self.node,
            gpu_node_id=self.gpu_node_id,
            exit_code=exit_code,
            msg=msg,
            start_time=self.start_time,
            end_time=self.end_time,
            job_id=self.job_id,
        )
        # Get writer from telemetry
        sink_impl = self.telem_registry[self.sink](
            **oc.from_dotlist(list(self.sink_opts))
        )
        clock = ClockImpl()
        log_time = clock.unixtime()
        try:
            sink_impl.write(
                data=Log(
                    ts=log_time,
                    message=[record],
                ),
                additional_params=SinkAdditionalParams(data_type=DataType.LOG),
            )
        except Exception:
            self.logger.exception("Telemetry failed with exception.")
        return False
