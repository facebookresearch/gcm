# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass
class HealthCheckLog:
    node: Optional[str]
    gpu_node_id: Optional[str]
    cluster: Optional[str]
    derived_cluster: Optional[str]
    health_check: Optional[str]
    type: Optional[str]
    result: Optional[int]
    # msg is a reserved word in cpython's logging module for LogRecord class:
    # KeyError: "Attempt to overwrite 'msg' in LogRecord"
    # see https://github.com/python/cpython/blob/3.10/Lib/logging/__init__.py#L1596
    _msg: Optional[str]
    job_id: Optional[int]
    start_time: Optional[float]
    end_time: Optional[float]
