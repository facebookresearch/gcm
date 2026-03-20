# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from unittest.mock import patch

from gcm.health_checks.checks.check_nvidia_smi import NvidiaSmiCliImpl
from gcm.monitoring.accelerator_adapter import AcceleratorTelemetryAdapter


def test_nvidia_smi_cli_impl_uses_hal_adapter() -> None:
    # Patch default_backend_factories to avoid actual registry access
    with (
        patch("gcm.health_checks.checks.check_nvidia_smi.default_backend_factories"),
        patch(
            "gcm.health_checks.checks.check_nvidia_smi.AcceleratorManager"
        ) as MockManager,
    ):
        # Mock manager instance
        manager_instance = MockManager.return_value

        cli = NvidiaSmiCliImpl(
            cluster="test_cluster", type="test_type", log_level="INFO", log_folder="."
        )
        telemetry = cli.get_device_telemetry()

        assert isinstance(telemetry, AcceleratorTelemetryAdapter)
        # Verify manager was initialized and probed
        MockManager.assert_called()
        manager_instance.probe_all.assert_called()
