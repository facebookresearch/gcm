# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest
from click.testing import CliRunner
from gcm.exporters.graph_api import to_scuba_message
from gcm.health_checks.check_utils.telem import get_telemetry_record
from gcm.health_checks.checks.check_nvidia_smi import check_nvidia_smi, NvidiaSmiCli
from gcm.health_checks.checks.check_telemetry import check_telemetry
from gcm.health_checks.types import ExitCode

from gcm.monitoring.device_telemetry_client import DeviceTelemetryClient, GPUDevice
from gcm.monitoring.meta_utils.scribe import ScribeConfig, write_messages
from gcm.monitoring.meta_utils.scuba import ScubaMessage
from gcm.schemas.health_check.health_check_name import HealthCheckName
from gcm.tests.config import Config
from gcm.tests.conftest import report_url

TEST_HEALTH_CHECK_SCRIBE_CATEGORY = "perfpipe_test_cluster_health"


def get_scribe_config(config: Config) -> ScribeConfig:
    return ScribeConfig(config.graph_api_access_token)


@report_url(("Scuba", "https://fburl.com/scuba/test_cluster_health/o3q4ug8o"))
def test_health_check_telemetry_publish_scribe(config: Config) -> None:
    """The scuba table for this test can be found here: https://fburl.com/scuba/test_cluster_health/6rwfwj5v"""
    record = get_telemetry_record(
        cluster="fair_cluster",
        derived_cluster="fair_cluster",
        type="nagios",
        health_check=HealthCheckName.CHECK_ZOMBIE.value,
        node="test_node",
        exit_code=ExitCode.OK,
        msg="This is a test write",
        gpu_node_id="123456",
        start_time=10.0,
        end_time=10.2,
        job_id=1,
    )

    scuba_msgs: List[ScubaMessage] = []
    scuba_msg: ScubaMessage = to_scuba_message(record)

    scuba_msgs.append(scuba_msg)

    current_time = int(time.time())

    write_messages(
        TEST_HEALTH_CHECK_SCRIBE_CATEGORY,
        scuba_msgs,
        get_scribe_config(config),
        current_time,
        60,
    )


def test_health_check_exception_unknown_to_scuba(
    tmp_path: Path,
    config: Config,
) -> None:
    class FakeDeviceTelemetryClient:
        devices: List[GPUDevice] = field(default_factory=list)

        def get_device_count(self) -> int:
            raise RuntimeError

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

    fake_nvidia_smi_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster", "type", "log_level", "log_folder"
    )
    runner = CliRunner(mix_stderr=False)

    with pytest.raises(RuntimeError):
        _ = runner.invoke(
            check_nvidia_smi,
            f"fair_cluster nagios --log-folder={tmp_path}  -c gpu_num --gpu_num=1 --sink=graph_api -o app_secret={config.graph_api_access_token} -o scribe_category=test_cluster_health",
            obj=fake_nvidia_smi_obj,
            catch_exceptions=False,
        )


@report_url(("Scuba", "https://fburl.com/scuba/test_cluster_health/o3q4ug8o"))
def test_health_check_check_telemetry(
    tmp_path: Path,
    config: Config,
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_telemetry,
        f'fair_cluster prolog --exit_code=2 --health-check-name="check zombie" --msg="unittest zombie" --node=node1000 --log-folder={tmp_path} --sink=graph_api -o app_secret={config.graph_api_access_token} -o scribe_category={TEST_HEALTH_CHECK_SCRIBE_CATEGORY}',
    )

    assert result.exit_code == ExitCode.OK.value


@report_url(
    (
        "Scuba heterogeneous cluster",
        "https://fburl.com/scuba/test_cluster_health/d1fsf78h",
    )
)
def test_health_check_check_telemetry_heterogeneous_cluster(
    tmp_path: Path,
    config: Config,
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_telemetry,
        f'fair_cluster prolog --exit_code=2 --heterogeneous-cluster-v1 --health-check-name="check zombie" --msg="unittest zombie" --node=node1000 --log-folder={tmp_path} --sink=graph_api -o app_secret={config.graph_api_access_token} -o scribe_category={TEST_HEALTH_CHECK_SCRIBE_CATEGORY}',
    )

    assert result.exit_code == ExitCode.OK.value
