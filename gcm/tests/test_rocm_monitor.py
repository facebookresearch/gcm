# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for rocm_monitor CLI."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

import pytest
from click.testing import CliRunner

from gcm.exporters.do_nothing import DoNothing
from gcm.monitoring.cli.rocm_monitor import (
    CliObject,
    main,
)
from gcm.monitoring.device_telemetry_client import DeviceTelemetryClient, GPUDevice
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.tests.fakes import FakeClock, FakeGPUDevice


@dataclass
class FakeTelemetryClient:
    devices: List[GPUDevice] = field(default_factory=list)

    def get_device_count(self) -> int:
        return len(self.devices)

    def get_device_by_index(self, index: int) -> GPUDevice:
        return self.devices[index]


@dataclass
class FakeRocmCliObject:
    clock: object = field(default_factory=FakeClock)
    registry: Mapping[str, Factory[SinkImpl]] = field(
        default_factory=lambda: {"do_nothing": DoNothing}
    )

    def get_device_telemetry(self) -> DeviceTelemetryClient:
        return FakeTelemetryClient(devices=[FakeGPUDevice()])

    def read_env(self, process_id: int) -> Dict[str, str]:
        return {}

    def get_ram_utilization(self) -> float:
        return 0.5

    def get_hostname(self) -> str:
        return "testhost"

    def format_epilog(self) -> str:
        return ""

    def looptimes(self, once: bool) -> Iterable[int]:
        return range(1)


def test_rocm_monitor_once(tmp_path: Path) -> None:
    """rocm_monitor --once runs one collection cycle and exits 0."""
    runner = CliRunner(mix_stderr=False)
    fake_obj: CliObject = FakeRocmCliObject()
    result = runner.invoke(
        main,
        [
            f"--log-folder={tmp_path}",
            "--collect-interval=1",
            "--push-interval=2",
            "--sink",
            "do_nothing",
            "--stdout",
            "--once",
            "--log-level=DEBUG",
        ],
        obj=fake_obj,
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    # One line per device (1) + one for host metrics
    lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
    assert len(lines) >= 1
