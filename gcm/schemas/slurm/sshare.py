# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass
class SshareRow:
    """sshare output schema.

    Fields correspond to sshare -P output columns.
    See https://slurm.schedmd.com/sshare.html
    """

    Account: str | None = None
    User: str | None = None
    RawShares: str | None = None
    NormShares: str | None = None
    RawUsage: str | None = None
    NormUsage: str | None = None
    EffectvUsage: str | None = None
    FairShare: str | None = None
    GrpTRESMins: str | None = None
    TRESRunMins: str | None = None


@dataclass(kw_only=True)
class SsharePayload(DerivedCluster):
    ds: str
    collection_unixtime: int
    cluster: str
    sshare: SshareRow
