# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import sys
from unittest.mock import patch

from gcm.health_checks.checks.check_nvidia_smi import NvidiaSmiCliImpl
from gcm.monitoring.accelerator_adapter import AcceleratorTelemetryAdapter


def test_nvidia_smi_cli_impl_uses_hal_adapter() -> None:
    # Patch default_backend_factories to avoid actual registry access
    # We use patch.object on the module to avoid ambiguity because
    # gcm.health_checks.checks.check_nvidia_smi resolves to the command function
    # when accessed via package attribute traversal in mock.patch string.
    module = sys.modules[NvidiaSmiCliImpl.__module__]
    with (
        patch.object(module, "default_backend_factories"),
        patch.object(module, "AcceleratorManager") as MockManager,
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
