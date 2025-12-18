# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, TypeVar


@dataclass
class JobInfo:
    # XXX: historically, -1 was used to signify no job is associated
    job_id: int = -1
    job_user: Optional[str] = None
    # comma separated list of GPU indices, e.g. '0,1,2,3'
    job_gpus: Optional[str] = None
    job_num_gpus: Optional[int] = None
    job_num_cpus: Optional[int] = None
    job_name: Optional[str] = None
    job_num_nodes: Optional[int] = None
    job_partition: Optional[str] = None

    # this is derived, so don't expose a parameter in init
    job_cpus_per_gpu: Optional[float] = field(default=None, init=False)

    def __post_init__(self) -> None:
        # Starting from SLURM v19, we use GPU_DEVICE_ORDINAL & SLURM_GPUS for GPU stats.
        # If this logic fails, we need to re-examine our understanding of SLURM env vars.
        if self.job_num_gpus is not None and self.job_gpus is not None:
            job_num_gpus = self.job_num_gpus
            job_gpus = self.job_gpus
            if job_num_gpus != len(job_gpus.split(",")):
                maybe_job_id = j if (j := self.job_id) is not None else "UNKNOWN"
                raise AssertionError(
                    f"SLURM_GPUS '{job_num_gpus}' does not match length of GPU IDs in "
                    f"GPU_DEVICE_ORDINAL '{job_gpus}' for job {maybe_job_id}"
                )

        def safe_maybe_div(
            maybe_dividend: Optional[int], maybe_divisor: Optional[int]
        ) -> Optional[float]:
            if maybe_dividend is None:
                return None

            if maybe_divisor is None or maybe_divisor == 0:
                return None

            return maybe_dividend / maybe_divisor

        self.job_cpus_per_gpu = safe_maybe_div(self.job_num_cpus, self.job_num_gpus)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "JobInfo":
        A = TypeVar("A")
        B = TypeVar("B")

        # Optional is a functor, so we can map functorially over it, i.e. "fmap"
        def fmap(f: Callable[[A], B], maybe_a: Optional[A]) -> Optional[B]:
            if maybe_a is None:
                return None
            return f(maybe_a)

        def get_num_gpus() -> Optional[int]:
            try:
                gpu_indices = env["SLURM_JOB_GPUS"]
            except KeyError:
                return fmap(int, env.get("SLURM_GPUS"))
            else:
                return gpu_indices.count(",") + 1

        return cls(
            # XXX: default value is -1 for legacy reasons; might be safe to keep as None
            # but to be safe let's keep it the same as before
            job_id=int(env.get("SLURM_JOB_ID", -1)),
            job_user=env.get("SLURM_JOB_USER"),
            job_gpus=env.get("GPU_DEVICE_ORDINAL"),
            job_num_gpus=get_num_gpus(),
            job_num_cpus=fmap(int, env.get("SLURM_CPUS_ON_NODE")),
            job_name=env.get("SLURM_JOB_NAME"),
            job_partition=env.get("SLURM_JOB_PARTITION"),
            job_num_nodes=fmap(int, env.get("SLURM_NNODES")),
        )
