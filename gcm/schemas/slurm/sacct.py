# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Hashable, Optional

from gcm.monitoring.clock import time_to_time_aware
from gcm.monitoring.coerce import maybe_float, maybe_int
from gcm.monitoring.slurm.nodelist_parsers import nodelist
from gcm.monitoring.slurm.parsing import (
    elapsed_string_to_seconds,
    parse_value_from_tres,
)

from gcm.schemas.dataclass import parsed_field
from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass(kw_only=True)
class SacctPayload(DerivedCluster):
    time: int
    end_ds: str
    cluster: str
    # Keys documented here: https://slurm.schedmd.com/sacct.html#lbAF
    sacct: dict[Hashable, str]


@dataclass(kw_only=True)
class Sacct(DerivedCluster):
    # Keys documented here: https://slurm.schedmd.com/sacct.html#lbAF
    Account: str = parsed_field(parser=str)
    AdminComment: str = parsed_field(parser=str)
    AllocCPUS: int | None = parsed_field(parser=maybe_int)
    AllocNodes: int | None = parsed_field(parser=maybe_int)
    AllocTRES: str = parsed_field(parser=str)
    AssocID: int | None = parsed_field(parser=maybe_int)
    AveCPU: float | None = parsed_field(parser=maybe_float)
    AveCPUFreq: float | None = parsed_field(parser=maybe_float)
    AveDiskRead: float | None = parsed_field(parser=maybe_float)
    AveDiskWrite: float | None = parsed_field(parser=maybe_float)
    AvePages: float | None = parsed_field(parser=maybe_float)
    AveRSS: float | None = parsed_field(parser=maybe_float)
    AveVMSize: float | None = parsed_field(parser=maybe_float)
    BlockID: str = parsed_field(parser=str)
    Cluster: str = parsed_field(parser=str)
    Comment: str = parsed_field(parser=str)
    Constraints: str = parsed_field(parser=str)
    ConsumedEnergy: str = parsed_field(parser=str)
    ConsumedEnergyRaw: str = parsed_field(parser=str)
    Container: str = parsed_field(parser=str)
    CPUTime: str = parsed_field(parser=str)
    CPUTimeRAW: int | None = parsed_field(parser=maybe_int)
    DBIndex: str = parsed_field(parser=str)
    DerivedExitCode: str = parsed_field(parser=str)
    Elapsed: str = parsed_field(parser=str)
    ElapsedRaw: int | None = parsed_field(parser=maybe_int)
    Eligible: str = parsed_field(parser=time_to_time_aware)
    End: str = parsed_field(parser=time_to_time_aware)
    ExitCode: str = parsed_field(parser=str)
    Flags: str = parsed_field(parser=str)
    GID: str = parsed_field(parser=str)
    Group: str = parsed_field(parser=str)
    JobID: str = parsed_field(parser=str)
    JobIDRaw: str = parsed_field(parser=str)
    JobName: str = parsed_field(parser=str)
    Layout: str = parsed_field(parser=str)
    MaxDiskRead: str = parsed_field(parser=str)
    MaxDiskReadNode: str = parsed_field(parser=str)
    MaxDiskReadTask: str = parsed_field(parser=str)
    MaxDiskWrite: str = parsed_field(parser=str)
    MaxDiskWriteNode: str = parsed_field(parser=str)
    MaxDiskWriteTask: str = parsed_field(parser=str)
    MaxPages: str = parsed_field(parser=str)
    MaxPagesNode: str = parsed_field(parser=str)
    MaxPagesTask: str = parsed_field(parser=str)
    MaxRSS: str = parsed_field(parser=str)
    MaxRSSNode: str = parsed_field(parser=str)
    MaxRSSTask: str = parsed_field(parser=str)
    MaxVMSize: str = parsed_field(parser=str)
    MaxVMSizeNode: str = parsed_field(parser=str)
    MaxVMSizeTask: str = parsed_field(parser=str)
    McsLabel: str = parsed_field(parser=str)
    MinCPU: str = parsed_field(parser=str)
    MinCPUNode: str = parsed_field(parser=str)
    MinCPUTask: str = parsed_field(parser=str)
    NCPUS: int | None = parsed_field(parser=maybe_int)
    NNodes: int | None = parsed_field(parser=maybe_int)
    NodeList: list[str] | None = parsed_field(parser=lambda s: nodelist()(s)[0])
    NTasks: int | None = parsed_field(parser=maybe_int)
    Partition: str = parsed_field(parser=str)
    Priority: str = parsed_field(parser=str)
    QOS: str = parsed_field(parser=str)
    QOSRAW: str = parsed_field(parser=str)
    Reason: str = parsed_field(parser=str)
    ReqCPUFreq: str = parsed_field(parser=str)
    ReqCPUFreqGov: str = parsed_field(parser=str)
    ReqCPUFreqMax: str = parsed_field(parser=str)
    ReqCPUFreqMin: str = parsed_field(parser=str)
    ReqCPUS: str = parsed_field(parser=str)
    ReqMem: str = parsed_field(parser=str)
    ReqNodes: str = parsed_field(parser=str)
    ReqTRES: str = parsed_field(parser=str)
    Reservation: str = parsed_field(parser=str)
    ReservationId: str = parsed_field(parser=str)
    Reserved: str = parsed_field(parser=str)
    ResvCPU: str = parsed_field(parser=str)
    ResvCPURAW: str = parsed_field(parser=str)
    Start: str = parsed_field(parser=time_to_time_aware)
    State: str = parsed_field(parser=str)
    Submit: str = parsed_field(parser=time_to_time_aware)
    SubmitLine: str = parsed_field(parser=str)
    Suspended: str = parsed_field(parser=str)
    SystemComment: str = parsed_field(parser=str)
    SystemCPU: str = parsed_field(parser=str)
    Timelimit: str = parsed_field(parser=str)
    TimelimitRaw: str = parsed_field(parser=str)
    TotalCPU: str = parsed_field(parser=str)
    TRESUsageInAve: str = parsed_field(parser=str)
    TRESUsageInMax: str = parsed_field(parser=str)
    TRESUsageInMaxNode: str = parsed_field(parser=str)
    TRESUsageInMaxTask: str = parsed_field(parser=str)
    TRESUsageInMin: str = parsed_field(parser=str)
    TRESUsageInMinNode: str = parsed_field(parser=str)
    TRESUsageInMinTask: str = parsed_field(parser=str)
    TRESUsageInTot: str = parsed_field(parser=str)
    TRESUsageOutAve: str = parsed_field(parser=str)
    TRESUsageOutMax: str = parsed_field(parser=str)
    TRESUsageOutMaxNode: str = parsed_field(parser=str)
    TRESUsageOutMaxTask: str = parsed_field(parser=str)
    TRESUsageOutMin: str = parsed_field(parser=str)
    TRESUsageOutMinNode: str = parsed_field(parser=str)
    TRESUsageOutMinTask: str = parsed_field(parser=str)
    TRESUsageOutTot: str = parsed_field(parser=str)
    UID: str = parsed_field(parser=str)
    User: str = parsed_field(parser=str)
    UserCPU: str = parsed_field(parser=str)
    WCKey: str = parsed_field(parser=str)
    WCKeyID: str = parsed_field(parser=str)
    WorkDir: str = parsed_field(parser=str)


@dataclass(kw_only=True)
class SacctMetrics(DerivedCluster):
    """Lightweight version of `class Sacct`, used for timeseries"""

    WaitingTime: Optional[float] = None
    # Keys documented here: https://slurm.schedmd.com/sacct.html#lbAF
    JobID: str = parsed_field(parser=str)
    User: str = parsed_field(parser=str)
    Account: str = parsed_field(parser=str)
    AllocCPUS: int = parsed_field(parser=int)
    AllocTRES: str = parsed_field(parser=str)
    ReqNodes: int = parsed_field(parser=int)
    ReqTRES: str = parsed_field(parser=str)
    Submit: str = parsed_field(parser=str)
    Start: str = parsed_field(parser=str)
    End: str = parsed_field(parser=str)
    State: str = parsed_field(parser=str)
    AllocNodes: int = parsed_field(parser=int)
    Elapsed: str = parsed_field(parser=str)
    Suspended: str = parsed_field(parser=str)
    AllocGPUS: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "gres/gpu"), field_name="AllocTRES"
    )
    ReqGPUS: int = parsed_field(
        parser=lambda s: parse_value_from_tres(s, "gres/gpu"), field_name="ReqTRES"
    )
    RunTimeSeconds: float = parsed_field(
        parser=lambda x: elapsed_string_to_seconds(x).total_seconds(),
        field_name="Elapsed",
    )
    SuspendedSeconds: float = parsed_field(
        parser=lambda x: elapsed_string_to_seconds(x).total_seconds(),
        field_name="Suspended",
    )
