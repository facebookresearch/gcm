# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Any, Dict

import pytest

from gcm.schemas.job_info import JobInfo
from typeguard import typechecked


class TestJobInfo:
    @staticmethod
    @pytest.mark.parametrize(
        "kwargs, expected_derived",
        [
            ({}, {"job_cpus_per_gpu": None}),
            ({"job_num_cpus": 10, "job_num_gpus": 0}, {"job_cpus_per_gpu": None}),
            ({"job_num_cpus": 10}, {"job_cpus_per_gpu": None}),
            ({"job_num_gpus": 1}, {"job_cpus_per_gpu": None}),
            ({"job_num_cpus": 10, "job_num_gpus": 2}, {"job_cpus_per_gpu": 5.0}),
        ],
    )
    def test_derived_attributes(
        kwargs: Dict[str, Any], expected_derived: Dict[str, Any]
    ) -> None:
        actual = JobInfo(**kwargs)

        for k, v in expected_derived.items():
            if isinstance(v, float):
                assert (
                    abs(getattr(actual, k) - v) < 1e-6
                ), f"Value mismatch on derived field '{k}'"
            else:
                assert getattr(actual, k) == v, f"Value mismatch on derived field '{k}'"

    @staticmethod
    def test_throws_if_num_gpus_and_gpus_are_inconsistent() -> None:
        with pytest.raises(AssertionError):
            JobInfo(job_gpus="0,1", job_num_gpus=1)

    @staticmethod
    @pytest.mark.parametrize(
        "env, expected",
        [
            (
                {
                    "SLURM_JOB_ID": "1234",
                    "SLURM_JOB_USER": "testuser",
                    "GPU_DEVICE_ORDINAL": "0,1",
                    "SLURM_JOB_GPUS": "0,1",
                    "SLURM_CPUS_ON_NODE": "20",
                    "SLURM_JOB_NAME": "testjob",
                    "SLURM_JOB_PARTITION": "testpartition",
                    "SLURM_NNODES": "1",
                },
                JobInfo(
                    job_id=1234,
                    job_user="testuser",
                    job_gpus="0,1",
                    job_num_gpus=2,
                    job_num_cpus=20,
                    job_name="testjob",
                    job_partition="testpartition",
                    job_num_nodes=1,
                ),
            ),
            # use SLURM_GPUS instead of SLURM_JOB_GPUS
            (
                {
                    "SLURM_JOB_ID": "1234",
                    "SLURM_JOB_USER": "testuser",
                    "GPU_DEVICE_ORDINAL": "0,1",
                    "SLURM_GPUS": "2",
                    "SLURM_CPUS_ON_NODE": "20",
                    "SLURM_JOB_NAME": "testjob",
                    "SLURM_JOB_PARTITION": "testpartition",
                    "SLURM_NNODES": "1",
                },
                JobInfo(
                    job_id=1234,
                    job_user="testuser",
                    job_gpus="0,1",
                    job_num_gpus=2,
                    job_num_cpus=20,
                    job_name="testjob",
                    job_partition="testpartition",
                    job_num_nodes=1,
                ),
            ),
            # GPU_DEVICE_ORDINAL is not defined
            (
                {
                    "SLURM_JOB_ID": "1234",
                    "SLURM_JOB_USER": "testuser",
                    "SLURM_GPUS": "2",
                    "SLURM_CPUS_ON_NODE": "20",
                    "SLURM_JOB_NAME": "testjob",
                    "SLURM_JOB_PARTITION": "testpartition",
                    "SLURM_NNODES": "1",
                },
                JobInfo(
                    job_id=1234,
                    job_user="testuser",
                    job_num_gpus=2,
                    job_num_cpus=20,
                    job_name="testjob",
                    job_partition="testpartition",
                    job_num_nodes=1,
                ),
            ),
            # CPU-only job
            (
                {
                    "SLURM_JOB_ID": "1234",
                    "SLURM_JOB_USER": "testuser",
                    "SLURM_CPUS_ON_NODE": "20",
                    "SLURM_JOB_NAME": "testjob",
                    "SLURM_JOB_PARTITION": "testpartition",
                    "SLURM_NNODES": "1",
                },
                JobInfo(
                    job_id=1234,
                    job_user="testuser",
                    job_num_cpus=20,
                    job_name="testjob",
                    job_partition="testpartition",
                    job_num_nodes=1,
                ),
            ),
        ],
    )
    @typechecked
    def test_from_env(env: Dict[str, str], expected: JobInfo) -> None:
        actual = JobInfo.from_env(env)

        assert actual == expected
