# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Tuple
from unittest.mock import patch

import psutil
import pynvml
import pytest
from click.testing import CliRunner
from gcm.health_checks.check_utils.pynvml_errors import error_exit_codes
from gcm.health_checks.checks.check_nvidia_smi import (
    check_app_clock_freq,
    check_nvidia_smi,
    NvidiaSmiCli,
)
from gcm.health_checks.types import ExitCode

from gcm.monitoring.device_telemetry_client import (
    ApplicationClockInfo,
    DeviceTelemetryClient,
    DeviceTelemetryException,
    GPUDevice,
    GPUMemory,
    ProcessInfo,
    RemappedRowInfo,
)

from gcm.tests.fakes import FakeGPUDevice, FakeProcess
from typeguard import typechecked


@dataclass
class FakeNvidiaSmiCliObject:
    cluster: str
    type: str
    log_level: str
    log_folder: str
    device_telemetry_client: DeviceTelemetryClient

    def get_device_telemetry(self) -> DeviceTelemetryClient:
        return self.device_telemetry_client


@pytest.mark.parametrize(
    "gpu_num, expected",
    [
        (
            8,
            (
                ExitCode.OK,
                "Number of GPUs present is the same as expected, 8",
            ),
        ),
        (
            6,
            (
                ExitCode.CRITICAL,
                "Number of GPUs present, 6, is different than expected, 8",
            ),
        ),
    ],
)
def test_check_gpu_num(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    gpu_num: int,
    expected: Tuple[ExitCode, str],
) -> None:
    class FakeDeviceTelemetryClient:
        devices: List[GPUDevice] = field(default_factory=list)

        def get_device_count(self) -> int:
            return gpu_num

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.devices[index]

    @dataclass
    class FakeNvidiaSmiCliObject:
        cluster: str
        type: str
        log_level: str
        log_folder: str

        def get_device_telemetry(self) -> DeviceTelemetryClient:
            return FakeDeviceTelemetryClient()

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster", "type", "log_level", "log_folder"
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_num --gpu_num=8",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "app_clock_info, expected",
    [
        (
            ApplicationClockInfo(1155, 1593),
            (ExitCode.OK, "Application frequencies are as expected."),
        ),
        (
            ApplicationClockInfo(10, 10),
            (
                ExitCode.CRITICAL,
                "GPU 0 has less application freq than expected. Expected: (GPU, GPU_mem) 1155, 1593 and got 10, 10.",
            ),
        ),
    ],
)
def test_check_app_clock_freq(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    app_clock_info: ApplicationClockInfo,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_clock_freq(self) -> ApplicationClockInfo:
            return app_clock_info

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c clock_freq --gpu_app_freq=1155 --gpu_app_mem_freq=1593",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "process_info, expected",
    [
        (
            [],
            (
                ExitCode.OK,
                "No other process is occupying any of the following GPUs: [0]",
            ),
        ),
        (
            [ProcessInfo(8, 0)],
            (ExitCode.CRITICAL, "GPU 0 is occupied by 1 other processes."),
        ),
    ],
)
def test_check_running_procs(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    process_info: List[ProcessInfo],
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_compute_processes(self) -> List[ProcessInfo]:
            return process_info

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    with (patch("psutil.pid_exists", return_value=True),):
        result = runner.invoke(
            check_nvidia_smi,
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c running_procs",
            obj=fake_nvidia_smi_obj,
        )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize("error_code, exception", list(error_exit_codes.items()))
@typechecked
def test_exception_handling(error_code: int, exception: Tuple[ExitCode, str]) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_clock_freq(self) -> ApplicationClockInfo:
            # raise Exception
            raise DeviceTelemetryException from pynvml.NVMLError(error_code)

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    logger = logging.getLogger(__name__)
    actual = check_app_clock_freq(FakeDeviceTelemetryClient(), 1155, 1593, logger)

    exception = (exception[0], f"clock_freq check: GPU 0: {exception[1]}")
    assert actual == exception


@typechecked
def test_pynvml_init_exception(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    @dataclass
    class FakeNvidiaSmiCliObjectInitException:
        cluster: str
        type: str
        log_level: str
        log_folder: str

        def get_device_telemetry(self) -> DeviceTelemetryClient:
            raise DeviceTelemetryException from pynvml.NVMLError(
                pynvml.NVML_ERROR_DRIVER_NOT_LOADED
            )

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObjectInitException(
        "cluster",
        "type",
        "log_level",
        "log_folder",
    )
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -c running_procs",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == ExitCode.WARN.value
    assert "Exception during pynvml init" in caplog.text


class CustomFakeGpuCliTestEnv(FakeGPUDevice):
    def get_compute_processes(self) -> List[ProcessInfo]:
        return []


@dataclass
class FakeNVMLDeviceTelemetryClientEnv:
    device: GPUDevice = field(default_factory=CustomFakeGpuCliTestEnv)

    def get_device_count(self) -> int:
        return 1

    def get_device_by_index(self, index: int) -> GPUDevice:
        return self.device


def test_check_running_procs_cli_env_devices_found(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeNVMLDeviceTelemetryClientEnv(),
    )
    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -c running_procs",
        obj=fake_nvidia_smi_obj,
        env={"CUDA_VISIBLE_DEVICES": "1"},
    )
    assert result.exit_code == 0
    assert "No other process is occupying any of the following GPUs: [1]" in caplog.text


@pytest.mark.parametrize(
    "attempt_process_info, pid_exists, force_kill, expected",
    [
        (
            # no process is occupying GPUs
            [[], [], []],
            True,
            False,
            (
                ExitCode.OK,
                "No other process is occupying any of the following GPUs: [0]",
            ),
        ),
        (
            # there are processes occupying GPUs after 3 tries
            [[ProcessInfo(8, 0)], [ProcessInfo(8, 0)], [ProcessInfo(8, 0)]],
            True,
            False,
            (ExitCode.CRITICAL, "GPU 0 is occupied by 1 other processes."),
        ),
        (
            # no process is occupying GPUs after 2nd try
            [[ProcessInfo(8, 0)], [], []],
            True,
            False,
            (
                ExitCode.WARN,
                "attempt #0: GPU 0 is occupied by 1 other processes.",
            ),
        ),
        (
            # no process is occupying GPUs after 3rd try
            [[ProcessInfo(8, 0)], [ProcessInfo(8, 0)], []],
            True,
            False,
            (
                ExitCode.WARN,
                "attempt #0: GPU 0 is occupied by 1 other processes.",
            ),
        ),
        (
            # force kill existed process. #3 is the processes list after force kill
            [[ProcessInfo(8, 0)], [ProcessInfo(8, 0)], [ProcessInfo(8, 0)], []],
            True,
            True,
            (ExitCode.OK, "force killed pids"),
        ),
        (
            # zombie processes
            [[ProcessInfo(8, 0)], [ProcessInfo(8, 0)], [ProcessInfo(8, 0)]],
            False,
            False,
            (ExitCode.OK, "found pids that are non existent but still occupy GPUs"),
        ),
        (
            # zombie processes with force kill existed process. #3 is the processes list after force kill
            [[ProcessInfo(8, 0)], [ProcessInfo(8, 0)], [ProcessInfo(8, 0)], []],
            False,
            True,
            (ExitCode.OK, "found pids that are non existent but still occupy GPUs"),
        ),
    ],
)
def test_check_and_kill_running_procs(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    attempt_process_info: List[List[ProcessInfo]],
    pid_exists: bool,
    force_kill: bool,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def __init__(self) -> None:
            self.attempt = -1

        def get_compute_processes(self) -> List[ProcessInfo]:
            self.attempt = self.attempt + 1
            return attempt_process_info[self.attempt]

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )
    fake_process: psutil.Process = FakeProcess(8, "")

    with (
        patch("time.sleep", return_value=None),
        patch("os.kill", return_value=None),
        patch("psutil.Process", return_value=fake_process),
        patch("psutil.pid_exists", return_value=pid_exists),
        patch("psutil.wait_procs", return_value=([], [])),
    ):
        result = runner.invoke(
            check_nvidia_smi,
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing --running_procs_force_kill {force_kill} -c running_procs_and_kill",
            obj=fake_nvidia_smi_obj,
        )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


def test_check_running_procs_cli_no_env_devices_found(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeNVMLDeviceTelemetryClientEnv(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -c running_procs",
        obj=fake_nvidia_smi_obj,
        env={"CUDA_VISIBLE_DEVICES": None},
    )
    assert result.exit_code == 0
    assert "No GPU devices were found" in caplog.text


def test_check_running_procs_cli_no_gpu_devices_found(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    class FakeNVMLDeviceTelemetryClient:
        def get_device_count(self) -> int:
            return 0

        def get_device_by_index(self, index: int) -> GPUDevice:
            return FakeGPUDevice()

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeNVMLDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c running_procs",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == 0
    assert "running_procs check: No GPU devices were found." in caplog.text


@pytest.mark.parametrize(
    "gpu_temp, expected",
    [
        (
            45,
            (
                ExitCode.OK,
                f"gpu_temp check: exit_code: {ExitCode.OK}, all GPU temperatures are lower than max threshold, 84.",
            ),
        ),
        (
            100,
            (
                ExitCode.CRITICAL,
                f"gpu_temp check: exit_code: {ExitCode.CRITICAL}, GPU 0 has temperature: 100, higher than critical threshold of 84.",
            ),
        ),
    ],
)
def test_check_gpu_temp(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    gpu_temp: int,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_temperature(self) -> int:
            return gpu_temp

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_temperature --gpu_temperature_threshold=84",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "memory_info, expected",
    [
        (
            GPUMemory(1000 * 1024 * 1024, 995 * 1024 * 1024, 5 * 1024 * 1024),
            (
                ExitCode.OK,
                "mem_usage check: all GPUs have mem usage lower than threshold: 15.",
            ),
        ),
        (
            GPUMemory(1000 * 1024 * 1024, 5 * 1024 * 1024, 995 * 1024 * 1024),
            (
                ExitCode.CRITICAL,
                "mem_usage check: GPU 0 mem usage: 995.0 is higher than threshold: 15.",
            ),
        ),
    ],
)
def test_check_mem_usage(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    memory_info: GPUMemory,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_memory_info(self) -> GPUMemory:
            return memory_info

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_mem_usage --gpu_mem_usage_threshold=15",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


class CustomFakeGpuCliMemUsageTestEnv(FakeGPUDevice):
    def get_memory_info(self) -> GPUMemory:
        return GPUMemory(1000 * 1024 * 1024, 995 * 1024 * 1024, 5 * 1024 * 1024)


def test_check_mem_usage_cli_env_devices_found(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeNVMLDeviceTelemetryClientEnv(CustomFakeGpuCliMemUsageTestEnv()),
    )
    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -c gpu_mem_usage --gpu_mem_usage_threshold=15",
        obj=fake_nvidia_smi_obj,
        env={"CUDA_VISIBLE_DEVICES": "1"},
    )
    assert result.exit_code == 0
    assert (
        "mem_usage check: all GPUs have mem usage lower than threshold: 15."
        in caplog.text
    )


def test_check_mem_usage_cli_no_env_devices_found(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeNVMLDeviceTelemetryClientEnv(CustomFakeGpuCliMemUsageTestEnv()),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -c gpu_mem_usage --gpu_mem_usage_threshold=15",
        obj=fake_nvidia_smi_obj,
        env={"CUDA_VISIBLE_DEVICES": None},
    )
    assert result.exit_code == 0
    assert "No GPU devices were found" in caplog.text


def test_check_mem_usage_cli_no_gpu_devices_found(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    class FakeNVMLDeviceTelemetryClient:
        def get_device_count(self) -> int:
            return 0

        def get_device_by_index(self, index: int) -> GPUDevice:
            return FakeGPUDevice()

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeNVMLDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_mem_usage --gpu_mem_usage_threshold=15",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == 0
    assert "mem_usage check: No GPU devices were found." in caplog.text


@pytest.mark.parametrize(
    "retired_pg_info, expected",
    [
        (
            (0, 0, 0),
            (
                ExitCode.OK,
                f"gpu_retired_pages check: exit_code: {ExitCode.OK}, all GPUs have pending retired pages and retired pages below the max threshold, 10",
            ),
        ),
        (
            (15, 0, 0),
            (
                ExitCode.CRITICAL,
                f"gpu_retired_pages check: exit_code: {ExitCode.CRITICAL}, GPU 0 has single/double/pending status pages: 15/0/0. Retired pages threshold is 10",
            ),
        ),
        (
            (0, 15, 0),
            (
                ExitCode.CRITICAL,
                f"gpu_retired_pages check: exit_code: {ExitCode.CRITICAL}, GPU 0 has single/double/pending status pages: 0/15/0. Retired pages threshold is 10",
            ),
        ),
        (
            (0, 0, 1),
            (
                ExitCode.CRITICAL,
                f"gpu_retired_pages check: exit_code: {ExitCode.CRITICAL}, GPU 0 has single/double/pending status pages: 0/0/1. Retired pages threshold is 10",
            ),
        ),
    ],
)
def test_check_gpu_retired_pages(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    retired_pg_info: Tuple[int, int, int],
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_retired_pages_multiple_single_bit_ecc_errors(
            self,
        ) -> Iterable[int]:
            return range(retired_pg_info[0])

        def get_retired_pages_double_bit_ecc_error(self) -> Iterable[int]:
            return range(retired_pg_info[1])

        def get_retired_pages_pending_status(self) -> int:
            return retired_pg_info[2]

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_retired_pages --gpu_retired_pages_threshold=10",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "ecc_uncorrected_total, expected",
    [
        (
            0,
            (
                ExitCode.OK,
                f"ecc_uncorrected_volatile_total check: exit_code: {ExitCode.OK}, all GPUs have ECC errors below the threshold of 0",
            ),
        ),
        (
            10,
            (
                ExitCode.CRITICAL,
                f"ecc_uncorrected_volatile_total check: exit_code: {ExitCode.CRITICAL}, GPU 0 has ECC uncorrected: 10 above the threshold of 0",
            ),
        ),
    ],
)
def test_check_ecc_uncorrected_volatile_total(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ecc_uncorrected_total: int,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_ecc_uncorrected_volatile_total(self) -> int:
            return ecc_uncorrected_total

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c ecc_uncorrected_volatile_total --ecc_uncorrected_volatile_threshold=0",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "ecc_corrected_total, expected",
    [
        (
            0,
            (
                ExitCode.OK,
                f"ecc_corrected_volatile_total check: exit_code: {ExitCode.OK}, all GPUs have ECC errors below the threshold of 10",
            ),
        ),
        (
            30,
            (
                ExitCode.CRITICAL,
                f"ecc_corrected_volatile_total check: exit_code: {ExitCode.CRITICAL}, GPU 0 has ECC corrected: 30 above the threshold of 10",
            ),
        ),
    ],
)
def test_check_ecc_corrected_volatile_total(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ecc_corrected_total: int,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_ecc_corrected_volatile_total(self) -> int:
            return ecc_corrected_total

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c ecc_corrected_volatile_total --ecc_corrected_volatile_threshold=10",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "row_remaps, expected",
    [
        (
            RemappedRowInfo(0, 0, 0, 0),
            (
                ExitCode.OK,
                f"row_remap check: exit_code: {ExitCode.OK}, all GPUs do not have row remap failures or pending remaps",
            ),
        ),
        (
            RemappedRowInfo(0, 0, 1, 0),
            (
                ExitCode.CRITICAL,
                f"row_remap check: exit_code: {ExitCode.CRITICAL}, GPU 0 has pending or failed row remaps: pending/failure/correctable/uncorrectable: 1/0/0/0",
            ),
        ),
        (
            RemappedRowInfo(0, 0, 0, 1),
            (
                ExitCode.CRITICAL,
                f"row_remap check: exit_code: {ExitCode.CRITICAL}, GPU 0 has pending or failed row remaps: pending/failure/correctable/uncorrectable: 0/1/0/0",
            ),
        ),
    ],
)
def test_check_row_remap(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    row_remaps: RemappedRowInfo,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_remapped_rows(self) -> RemappedRowInfo:
            return row_remaps

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c row_remap",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "row_remaps, expected",
    [
        (
            RemappedRowInfo(0, 0, 0, 0),
            (
                ExitCode.OK,
                f"row_remap_pending check: exit_code: {ExitCode.OK}, all GPUs do not have pending remaps",
            ),
        ),
        (
            RemappedRowInfo(0, 0, 1, 0),
            (
                ExitCode.CRITICAL,
                f"row_remap_pending check: exit_code: {ExitCode.CRITICAL}, GPU 0 has pending row remaps: pending/failure/correctable/uncorrectable: 1/0/0/0",
            ),
        ),
        (
            RemappedRowInfo(0, 0, 0, 1),
            (
                ExitCode.OK,
                f"row_remap_pending check: exit_code: {ExitCode.OK}, all GPUs do not have pending remaps",
            ),
        ),
    ],
)
def test_check_row_remap_pending(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    row_remaps: RemappedRowInfo,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_remapped_rows(self) -> RemappedRowInfo:
            return row_remaps

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c row_remap_pending",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "row_remaps, expected",
    [
        (
            RemappedRowInfo(0, 0, 0, 0),
            (
                ExitCode.OK,
                f"row_remap_failed check: exit_code: {ExitCode.OK}, all GPUs do not have row remap failures",
            ),
        ),
        (
            RemappedRowInfo(0, 0, 0, 1),
            (
                ExitCode.CRITICAL,
                f"row_remap_failed check: exit_code: {ExitCode.CRITICAL}, GPU 0 has failed row remaps: pending/failure/correctable/uncorrectable: 0/1/0/0",
            ),
        ),
        (
            RemappedRowInfo(0, 0, 1, 0),
            (
                ExitCode.OK,
                f"row_remap_failed check: exit_code: {ExitCode.OK}, all GPUs do not have row remap failures",
            ),
        ),
    ],
)
def test_check_row_remap_failed(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    row_remaps: RemappedRowInfo,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def get_remapped_rows(self) -> RemappedRowInfo:
            return row_remaps

    class FakeDeviceTelemetryClient:
        device: GPUDevice = CustomFakeGpu()

        def get_device_count(self) -> int:
            return 1

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.device

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    result = runner.invoke(
        check_nvidia_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c row_remap_failed",
        obj=fake_nvidia_smi_obj,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "vbios_list, vbios, expected",
    [
        (
            ["86.00.4D.00.04", "86.00.4D.00.04"],
            "86.00.4D.00.04",
            (
                ExitCode.OK,
                f"vbios mismatch check: exit_code: {ExitCode.OK}, all GPUs have a consistent vbios version.\n",
            ),
        ),
        (
            ["86.00.4D.00.04", "86.00.4D.00.04"],
            "86.00.4D.10.04",
            (
                ExitCode.CRITICAL,
                f"vbios mismatch mismatch: exit_code: {ExitCode.CRITICAL}, Expect '86.00.4D.10.04' Found '86.00.4D.00.04'\n",
            ),
        ),
        (
            ["86.00.4D.00.04", "86.00.4D.10.04", "86.00.4D.00.04", "86.00.4D.00.04"],
            "86.00.4D.00.04",
            (
                ExitCode.CRITICAL,
                f"vbios mismatch mismatch: exit_code: {ExitCode.CRITICAL}, Expect '86.00.4D.00.04' Found '86.00.4D.10.04'\n",
            ),
        ),
        (
            ["86.00.4D.00.04", "", "86.00.4D.00.04", "86.00.4D.00.04"],
            "86.00.4D.00.04",
            (
                ExitCode.CRITICAL,
                f"vbios mismatch mismatch: exit_code: {ExitCode.CRITICAL}, Expect '86.00.4D.00.04' Found ''\n",
            ),
        ),
        # not provided expected vbios
        (
            ["86.00.4D.00.04", "86.00.4D.00.04"],
            "",
            (
                ExitCode.OK,
                f"vbios mismatch check: exit_code: {ExitCode.OK}, all GPUs have a consistent vbios version.\n",
            ),
        ),
        (
            ["86.00.4D.00.04", "86.00.4D.10.04", "86.00.4D.00.04", "86.00.4D.00.04"],
            "",
            (
                ExitCode.CRITICAL,
                f"vbios mismatch mismatch: exit_code: {ExitCode.CRITICAL}, Expect '86.00.4D.00.04' Found '86.00.4D.10.04'\n",
            ),
        ),
        (
            ["86.00.4D.00.04", "", "86.00.4D.00.04", "86.00.4D.00.04"],
            "",
            (
                ExitCode.CRITICAL,
                f"vbios mismatch mismatch: exit_code: {ExitCode.CRITICAL}, Expect '86.00.4D.00.04' Found ''\n",
            ),
        ),
    ],
)
def test_vbios_mismatch(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    vbios_list: List[str],
    vbios: str,
    expected: Tuple[ExitCode, str],
) -> None:
    class CustomFakeGpu(FakeGPUDevice):
        def __init__(self, vbios: str) -> None:
            self.vbios = vbios

        def get_vbios_version(self) -> str:
            return self.vbios

    class FakeDeviceTelemetryClient:
        def __init__(self) -> None:
            self.devices = [CustomFakeGpu(vbios) for vbios in vbios_list]

        def get_device_count(self) -> int:
            return len(vbios_list)

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.devices[index]

    runner = CliRunner(mix_stderr=False)

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        FakeDeviceTelemetryClient(),
    )

    if vbios == "":
        result = runner.invoke(
            check_nvidia_smi,
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c vbios_mismatch",
            obj=fake_nvidia_smi_obj,
        )
    else:
        result = runner.invoke(
            check_nvidia_smi,
            f"fair_cluster nagios --log-folder={tmp_path} --gpu_vbios {vbios} --sink=do_nothing -c vbios_mismatch",
            obj=fake_nvidia_smi_obj,
        )
    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
