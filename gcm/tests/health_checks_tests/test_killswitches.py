# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from pathlib import Path
from typing import Generator

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_nvidia_smi import NvidiaSmiCli
from gcm.health_checks.cli.health_checks import health_checks as hc_main
from gcm.health_checks.types import ExitCode

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.tests.health_checks_tests.test_nvidia_smi import (
    FakeNvidiaSmiCliObject,
    FakeNVMLDeviceTelemetryClientEnv,
)
from typeguard import typechecked


@pytest.fixture(scope="module", autouse=True)
def cleanup_config_path() -> Generator[None, None, None]:
    yield
    FeatureValueHealthChecksFeatures.config_path = None


def _write_to_file(path: Path, data: str) -> Path:
    with path.open("w") as f:
        f.write(data)
    return path


@pytest.mark.parametrize(
    "command",
    [
        "check-process check-zombie",
        "cuda memtest",
        "check-syslogs link-flaps",
        "check-syslogs xid",
        "check-syslogs io-errors",
        "check-processor processor-freq",
        "check-processor cpufreq-governor",
        "check-processor check-mem-size",
        "check-ipmitool check-sel",
        "check-hca --expected-count=4",
        "check-storage disk-usage -v sth",
        "check-storage mounted-directory -d sth",
        "check-storage file-exists -f sth",
        "check-storage directory-exists -d sth",
        "check-storage check-mountpoint --mountpoint=/checkpoint/",
        "check-process check-running-process -p sth",
        "check-service ssh-connection --host=sth",
        "check-service node-slurm-state",
        "check-service slurmctld-count --slurmctld-count=100",
        "check-service cluster-availability",
        "check-service service-status -s sth",
        "check-service package-version -p sth -v sth",
        "check-nccl --nccl-tdir=sth -p all_gather --critical-threshold=4",
        "check-nvidia-smi -c gpu_num",
        "check-nvidia-smi -c running_procs",
        "check-nvidia-smi -c clock_freq",
        "check-nvidia-smi -c gpu_temperature --gpu_temperature_threshold=1",
        "check-nvidia-smi -c gpu_mem_usage",
        "check-nvidia-smi -c gpu_retired_pages",
        "check-nvidia-smi -c ecc_uncorrected_volatile_total",
        "check-nvidia-smi -c ecc_corrected_volatile_total",
        "check-nvidia-smi -c row_remap",
        "check-dcgmi diag",
        "check-dcgmi nvlink -c nvlink_errors",
        "check-dcgmi nvlink -c nvlink_status",
        "check-ib check-ibstat",
        "check-ib check-ib-interfaces",
        "check-authentication password-status",
        "check-node uptime",
        "check-node check-module -m sth",
        "check-node check-dnf-repos",
        "check-sensors",
    ],
)
@typechecked
def test_killswitches(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, command: str
) -> None:
    runner = CliRunner(mix_stderr=False)
    config_path = _write_to_file(
        tmp_path / "killswitches.toml",
        """
        [HealthChecksFeatures]
        disable_cuda_memtest = true
        disable_check_zombie = true
        disable_link_flap = true
        disable_xid_errors = true
        disable_io_errors = true
        disable_proc_freq = true
        disable_freq_governor = true
        disable_check_mem_size = true
        disable_ipmi_sel = true
        disable_hca_count = true
        disable_disk_usage = true
        disable_disk_size = true
        disable_mounted_dir = true
        disable_file_exists = true
        disable_dir_exists = true
        disable_check_mountpoint = true
        disable_running_process = true
        disable_check_ssh = true
        disable_slurm_state = true
        disable_slrmctld_count = true
        disable_slurm_cluster_avail = true
        disable_service_status = true
        disable_package_version = true
        disable_nccl_tests = true
        disable_nvidia_smi_gpu_num = true
        disable_nvidia_smi_clock_freq = true
        disable_nvidia_smi_running_procs = true
        disable_nvidia_smi_gpu_temp = true
        disable_nvidia_smi_mem_usage = true
        disable_nvidia_smi_retired_pages = true
        disable_nvidia_smi_ecc_uncorrected = true
        disable_nvidia_smi_ecc_corrected = true
        disable_nvidia_smi_row_remap = true
        disable_dcgmi_diag = true
        disable_dcgmi_nvlink = true
        disable_dcgmi_nvlink_error = true
        disable_dcgmi_nvlink_status = true
        disable_check_ibstat = true
        disable_check_ib_interfaces = true
        disable_pass_status = true
        disable_user_access_path_check = true
        disable_check_uptime = true
        disable_check_module = true
        disable_check_dnf_repos = true
        disable_check_sensors = true
        """,
    )

    if "nvidia-smi" in command:
        fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
            "cluster",
            "type",
            "log_level",
            "log_folder",
            FakeNVMLDeviceTelemetryClientEnv(),
        )
        result = runner.invoke(
            hc_main,
            f"--features-config={config_path} {command} fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing",
            catch_exceptions=False,
            obj=fake_nvidia_smi_obj,
        )
    else:
        result = runner.invoke(
            hc_main,
            f"--features-config={config_path} {command} fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing",
            catch_exceptions=False,
        )

    assert result.exit_code == ExitCode.OK.value
    assert "disabled by killswitch" in caplog.text
