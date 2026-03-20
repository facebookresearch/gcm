# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from unittest.mock import patch

from gcm.monitoring.accelerator_adapter import AcceleratorTelemetryAdapter
from gcm.monitoring.cli.nvml_monitor import CliObjectImpl


def test_cli_object_impl_uses_hal_adapter() -> None:
    # Patch default_backend_factories to avoid actual registry access
    with (
        patch("gcm.monitoring.cli.nvml_monitor.default_backend_factories"),
        patch("gcm.monitoring.cli.nvml_monitor.AcceleratorManager") as MockManager,
    ):
        # Mock manager instance
        manager_instance = MockManager.return_value

        cli = CliObjectImpl()
        telemetry = cli.get_device_telemetry()

        assert isinstance(telemetry, AcceleratorTelemetryAdapter)
        # Verify manager was initialized and probed
        MockManager.assert_called()
        manager_instance.probe_all.assert_called()
