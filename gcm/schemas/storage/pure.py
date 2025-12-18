# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional

from gcm.monitoring.slurm.parsing import parse_job_ids
from gcm.monitoring.utils.parsing.storage import parse_abbreviated_float
from gcm.schemas.dataclass import parsed_field


@dataclass
class PureInfo:
    """
    {
        "user":<user_id>,
        "used":<usage_in_bytes>,
        "sample_time":<time in unixtime>,
        "directory":<usage within which directory>
    }
    """

    cluster: str
    user: int
    used_bytes: int
    sample_time: int
    directory: str
    username: Optional[str] = None


@dataclass
class PureData:
    cluster: str
    flashblade: str
    hostname: str = parsed_field(parser=str, field_name="NAME")
    read_throughput_bytes_per_sec: float = parsed_field(
        parser=parse_abbreviated_float, field_name="B/s(r)"
    )
    write_throughput_bytes_per_sec: float = parsed_field(
        parser=parse_abbreviated_float, field_name="B/s(r)"
    )
    read_freq_op_per_sec: float = parsed_field(
        parser=parse_abbreviated_float, field_name="op/s(r)"
    )
    write_freq_op_per_sec: float = parsed_field(
        parser=parse_abbreviated_float, field_name="op/s(w)"
    )
    other_freq_op_per_sec: float = parsed_field(
        parser=parse_abbreviated_float, field_name="op/s(o)"
    )
    read_latency_us_per_op: float = parsed_field(parser=float, field_name="us/op(r)")
    write_latency_us_per_op: float = parsed_field(parser=float, field_name="us/op(w)")
    other_latency_us_per_op: float = parsed_field(
        parser=float, field_name="us/op(other)"
    )
    job_ids: list[str] = parsed_field(parser=parse_job_ids, field_name="JOBIDS")
