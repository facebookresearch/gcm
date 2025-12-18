# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, fields
from typing import cast, Optional, TYPE_CHECKING

from gcm.schemas.job_info import JobInfo
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass
class DeviceMetrics:
    mem_util: Optional[int] = None
    mem_used_percent: Optional[int] = None
    gpu_util: Optional[int] = None
    temperature: Optional[int] = None
    power_draw: Optional[int] = None
    power_used_percent: Optional[int] = None
    retired_pages_count_single_bit: Optional[int] = None
    retired_pages_count_double_bit: Optional[int] = None

    @typechecked
    def __add__(self, other: JobInfo) -> "DevicePlusJobMetrics":
        dev_job_metrics = DevicePlusJobMetrics()

        for obj in [self, other]:
            for _field in fields(cast(DataclassInstance, obj)):
                setattr(dev_job_metrics, _field.name, getattr(obj, _field.name))

        return dev_job_metrics


@dataclass
class DevicePlusJobMetrics(DeviceMetrics, JobInfo):
    gpu_id: Optional[int] = None
    hostname: Optional[str] = None
    job_cpus_per_gpu: Optional[float] = None
