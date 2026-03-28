# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import dataclass, field
from itertools import cycle
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from gcm.exporters.do_nothing import DoNothing

from gcm.monitoring.cli.nvml_monitor import (
    CliObject,
    CliObjectImpl,
    get_ram_utilization,
    main,
    read_environ_from_proc,
    retrieve_job_on_gpu,
)
from gcm.monitoring.clock import Clock
from gcm.monitoring.device_telemetry_client import (
    ApplicationClockInfo,
    DeviceTelemetryClient,
    GPUDevice,
    GPUMemory,
    GPUUtilization,
    ProcessInfo,
    RemappedRowInfo,
)
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.schemas.job_info import JobInfo
from gcm.tests.fakes import FakeClock, FakeGPUDevice
from typeguard import typechecked


def test_retrieve_job_on_gpu() -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_compute_processes(self) -> List[ProcessInfo]:
            return [
                ProcessInfo(pid=1234, usedGpuMemory=300),
                ProcessInfo(pid=4567, usedGpuMemory=400),
            ]

    fake_handle = CustomFakeGpu()
    expected = JobInfo(
        job_id=1234,
        job_user="testuser",
        job_gpus="0,1",
        job_num_gpus=2,
        job_num_cpus=20,
        job_name="testjob",
        job_partition="testpartition",
        job_num_nodes=1,
    )

    def fake_env_reader(pid: int) -> Dict[str, str]:
        envs = {
            1234: {
                "SLURM_JOB_ID": "1234",
                "SLURM_JOB_USER": "testuser",
                "GPU_DEVICE_ORDINAL": "0,1",
                "SLURM_JOB_GPUS": "0,1",
                "SLURM_CPUS_ON_NODE": "20",
                "SLURM_JOB_NAME": "testjob",
                "SLURM_JOB_PARTITION": "testpartition",
                "SLURM_NNODES": "1",
            },
            4567: {
                "SLURM_JOB_ID": "1235",
                "SLURM_JOB_USER": "testuser2",
                "GPU_DEVICE_ORDINAL": "2,3,4,5",
                "SLURM_JOB_GPUS": "0,1,2,3",
                "SLURM_CPUS_ON_NODE": "40",
                "SLURM_JOB_NAME": "testjob2",
                "SLURM_JOB_PARTITION": "testpartition",
                "SLURM_NNODES": "1",
            },
        }
        return envs[pid]

    actual = retrieve_job_on_gpu(fake_handle, env_reader=fake_env_reader)

    assert actual == expected


def test_retrieve_job_on_gpu_no_processes() -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_compute_processes(self) -> List[ProcessInfo]:
            return []

    fake_handle = CustomFakeGpu()
    fake_env_reader = MagicMock()

    actual = retrieve_job_on_gpu(fake_handle, env_reader=fake_env_reader)

    assert actual is None
    fake_env_reader.assert_not_called()


def test_retrieve_job_on_gpu_get_compute_processes_throws() -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_compute_processes(self) -> List[ProcessInfo]:
            raise Exception

    fake_handle = CustomFakeGpu()
    fake_env_reader = MagicMock()

    actual = retrieve_job_on_gpu(fake_handle, env_reader=fake_env_reader)

    assert actual is None
    fake_env_reader.assert_not_called()


@pytest.mark.parametrize(
    "contents, expected",
    [
        ("FOO=bar", {"FOO": "bar"}),
        ("FOO=bar\x00baz=QUUX", {"FOO": "bar", "baz": "QUUX"}),
        ("", {}),
        ("FOO=bar=baz", {"FOO": "bar=baz"}),
    ],
)
@typechecked
def test_read_environ_from_proc(contents: str, expected: Dict[str, str]) -> None:
    fake_run_cmd = MagicMock()
    fake_run_cmd.return_value = contents

    actual = read_environ_from_proc(1234, run_cmd=fake_run_cmd)

    assert actual == expected
    fake_run_cmd.assert_called_once()


def test_get_ram_utilization() -> None:
    fake_get_command_output = MagicMock()
    fake_get_command_output.return_value = (
        "              total        used        free      shared  buff/cache   available\n"
        "Mem:         772649       22167        6005       19728      744476      727226\n"
        "Swap:         65535       27025       38510\n"
    )

    actual = get_ram_utilization(get_command_output=fake_get_command_output)

    assert abs(actual - 0.02868961) < 1e-6


@dataclass
class IteratorFakeGPUDevice:
    power_usage: Iterator[int]
    temp: Iterator[int]
    memory_info: Iterator[GPUMemory]
    utilization: Iterator[GPUUtilization]
    power_limit: int
    retired_pages_double_bit_ecc_error: List[int]
    retired_pages_multiple_single_bit_ecc_errors: List[int]
    application_clock_info: ApplicationClockInfo = field(
        default_factory=lambda: ApplicationClockInfo(
            graphics_freq=1155, memory_freq=1593
        )
    )

    def get_compute_processes(self) -> List[ProcessInfo]:
        processes = [(1, 87), (2, 90), (3, 15)]
        return [ProcessInfo(pid, gpu_memory) for pid, gpu_memory in processes]

    def get_retired_pages_double_bit_ecc_error(self) -> Iterable[int]:
        return self.retired_pages_double_bit_ecc_error

    def get_retired_pages_multiple_single_bit_ecc_errors(
        self,
    ) -> Iterable[int]:
        return self.retired_pages_multiple_single_bit_ecc_errors

    def get_retired_pages_pending_status(self) -> int:
        return 0

    def get_remapped_rows(self) -> RemappedRowInfo:
        return RemappedRowInfo(0, 0, 0, 0)

    def get_ecc_uncorrected_volatile_total(self) -> int:
        return 0

    def get_ecc_corrected_volatile_total(self) -> int:
        return 0

    def get_enforced_power_limit(self) -> Optional[int]:
        return self.power_limit

    def get_power_usage(self) -> Optional[int]:
        return next(self.power_usage)

    def get_temperature(self) -> int:
        return next(self.temp)

    def get_memory_info(self) -> GPUMemory:
        return next(self.memory_info)

    def get_utilization_rates(self) -> GPUUtilization:
        return next(self.utilization)

    def get_clock_freq(self) -> ApplicationClockInfo:
        return self.application_clock_info

    def get_vbios_version(self) -> str:
        return "86.00.4D.00.04"


@dataclass
class FakeTelemetryClient:
    devices: List[GPUDevice] = field(default_factory=list)

    def get_device_count(self) -> int:
        return len(self.devices)

    def get_device_by_index(self, index: int) -> GPUDevice:
        return self.devices[index]


@dataclass
class FakeNvmlCliObject(CliObjectImpl):
    clock: Clock = field(default_factory=FakeClock)
    registry: Mapping[str, Factory[SinkImpl]] = field(
        default_factory=lambda: {"do_nothing": DoNothing}
    )

    def get_device_telemetry(self) -> DeviceTelemetryClient:
        return fake_telemetry_client()

    def read_env(self, process_id: int) -> Dict[str, str]:
        envs = {
            1: {
                "SLURM_JOB_ID": "1234",
                "SLURM_JOB_USER": "testuser",
                "GPU_DEVICE_ORDINAL": "0",
                "SLURM_JOB_GPUS": "0",
                "SLURM_CPUS_ON_NODE": "20",
                "SLURM_JOB_NAME": "testjob",
                "SLURM_JOB_PARTITION": "testpartition",
                "SLURM_NNODES": "1",
            },
            2: {
                "SLURM_JOB_ID": "1235",
                "SLURM_JOB_USER": "testuser2",
                "GPU_DEVICE_ORDINAL": "2,3",
                "SLURM_JOB_GPUS": "0,1",
                "SLURM_CPUS_ON_NODE": "40",
                "SLURM_JOB_NAME": "testjob2",
                "SLURM_JOB_PARTITION": "testpartition",
                "SLURM_NNODES": "1",
            },
            3: {
                "SLURM_JOB_ID": "1236",
                "SLURM_JOB_USER": "testuser2",
                "SLURM_CPUS_ON_NODE": "20",
                "SLURM_JOB_NAME": "testjob3",
                "SLURM_JOB_PARTITION": "testpartition",
                "SLURM_NNODES": "1",
            },
        }
        return envs[process_id]

    def get_ram_utilization(self) -> float:
        return 79.3

    def get_hostname(self) -> str:
        return "testhost"

    def format_epilog(self) -> str:
        return ""

    def looptimes(self, once: bool) -> Iterable[int]:
        return range(1)


def fake_telemetry_client() -> DeviceTelemetryClient:
    return FakeTelemetryClient(
        devices=[
            IteratorFakeGPUDevice(
                power_limit=100,
                power_usage=iter(cycle([90, 80])),
                temp=iter(cycle([42, 38])),
                memory_info=iter(
                    cycle(
                        [
                            GPUMemory(total=100, free=20, used=80),
                            GPUMemory(total=100, free=10, used=90),
                        ]
                    )
                ),
                utilization=iter(
                    cycle(
                        [
                            GPUUtilization(gpu=70, memory=80),
                            GPUUtilization(gpu=80, memory=90),
                        ]
                    )
                ),
                retired_pages_multiple_single_bit_ecc_errors=[1, 2],
                retired_pages_double_bit_ecc_error=[3, 4, 5],
            ),
            IteratorFakeGPUDevice(
                power_limit=100,
                power_usage=iter(cycle([91, 81])),
                temp=iter(cycle([45, 42])),
                memory_info=iter(
                    cycle(
                        [
                            GPUMemory(total=100, free=19, used=81),
                            GPUMemory(total=100, free=11, used=89),
                        ]
                    )
                ),
                utilization=iter(
                    cycle(
                        [
                            GPUUtilization(gpu=69, memory=81),
                            GPUUtilization(gpu=81, memory=95),
                        ]
                    )
                ),
                retired_pages_multiple_single_bit_ecc_errors=[],
                retired_pages_double_bit_ecc_error=[1],
            ),
        ]
    )


def test_cli(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj: CliObject = FakeNvmlCliObject()
    expected_device_0_metrics = {
        "gpu_id": 0,
        "hostname": "testhost",
        "mem_util": 90,
        "gpu_util": 80,
        "temperature": 42,
        "power_draw": 90,
        "power_used_percent": 90,
        "retired_pages_count_single_bit": 2,
        "retired_pages_count_double_bit": 3,
        "job_id": 1234,
        "job_user": "testuser",
        "job_gpus": "0",
        "job_num_gpus": 1,
        "job_num_cpus": 20,
        "job_name": "testjob",
        "job_num_nodes": 1,
        "job_cpus_per_gpu": 20.0,
        "job_partition": "testpartition",
    }
    expected_device_1_metrics = {
        "gpu_id": 1,
        "hostname": "testhost",
        "mem_util": 95,
        "gpu_util": 81,
        "temperature": 45,
        "power_draw": 91,
        "power_used_percent": 91,
        "retired_pages_count_single_bit": 0,
        "retired_pages_count_double_bit": 1,
    }
    expected_host_metrics = {
        "max_gpu_util": 81,
        "min_gpu_util": 80,
        "avg_gpu_util": 80.5,
        "ram_util": 79.3,
    }

    result = runner.invoke(
        main,
        [
            f"--log-folder={tmp_path}",
            "--collect-interval=1",
            "--push-interval=5",
            "--sink",
            "do_nothing",
            "--stdout",
            "--once",
            "--log-level=DEBUG",
        ],
        obj=fake_obj,
        catch_exceptions=False,
    )

    lines = result.stdout.strip().split("\n")
    # one for each device (there are two) and one for host metrics
    assert len(lines) == 3, result.stdout

    # we don't _really_ care if extra data is collected
    actual_device_0_metrics = json.loads(lines[0].split("- ")[2])
    for k, v in expected_device_0_metrics.items():
        assert actual_device_0_metrics[k] == v, f"Value mismatch for key '{k}'"

    actual_device_1_metrics = json.loads(lines[1].split("- ")[2])
    for k, v in expected_device_1_metrics.items():
        assert actual_device_1_metrics[k] == v, f"Value mismatch for key '{k}'"

    actual_host_metrics = json.loads(lines[2].split("- ")[2])
    for k, v in expected_host_metrics.items():
        assert actual_host_metrics[k] == v, f"Value mismatch for key '{k}'"


def test_cli_run_interval(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj: CliObject = FakeNvmlCliObject()

    result = runner.invoke(
        main,
        [
            f"--log-folder={tmp_path}",
            "--push-interval=5",
            "--interval=60",
            "--sink",
            "do_nothing",
            "--once",
            "--stdout",
            "--log-level=DEBUG",
        ],
        obj=fake_obj,
        catch_exceptions=True,
    )
    # Expected output from FakeNvmlCliObject
    expected_device_0_info = {
        "gpu_id": 0,
        "gpu_util": 70,
        "hostname": "testhost",
        "job_cpus_per_gpu": 20,
        "job_gpus": "0",
        "job_id": 1234,
        "job_name": "testjob",
        "job_num_cpus": 20,
        "job_num_gpus": 1,
        "job_num_nodes": 1,
        "job_partition": "testpartition",
        "job_user": "testuser",
        "mem_used_percent": 80,
        "mem_util": 80,
        "power_draw": 90,
        "power_used_percent": 90,
        "retired_pages_count_double_bit": 3,
        "retired_pages_count_single_bit": 2,
        "temperature": 42,
    }
    expected_device_1_info = {
        "gpu_id": 1,
        "gpu_util": 69,
        "hostname": "testhost",
        "job_cpus_per_gpu": 20,
        "job_gpus": "0",
        "job_id": 1234,
        "job_name": "testjob",
        "job_num_cpus": 20,
        "job_num_gpus": 1,
        "job_num_nodes": 1,
        "job_partition": "testpartition",
        "job_user": "testuser",
        "mem_used_percent": 81,
        "mem_util": 81,
        "power_draw": 91,
        "power_used_percent": 91,
        "retired_pages_count_double_bit": 1,
        "retired_pages_count_single_bit": 0,
        "temperature": 45,
    }
    expected_util_info = {
        "avg_gpu_util": 69.5,
        "max_gpu_util": 70,
        "min_gpu_util": 69,
        "ram_util": 79.3,
    }
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0].split("- ")[2]) == expected_device_0_info
    assert json.loads(lines[1].split("- ")[2]) == expected_device_1_info
    assert json.loads(lines[2].split("- ")[2]) == expected_util_info
    assert result.exit_code == 0
