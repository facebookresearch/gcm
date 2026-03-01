# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for the HealthCheckRuntime context manager."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.types import ExitCode
from gcm.schemas.health_check.health_check_name import HealthCheckName


def _make_runtime(**kwargs) -> HealthCheckRuntime:
    defaults = dict(
        cluster="test_cluster",
        type="prolog",
        log_level="INFO",
        log_folder="/tmp",
        sink="do_nothing",
        sink_opts=(),
        verbose_out=False,
        heterogeneous_cluster_v1=False,
        health_check_name=HealthCheckName.CHECK_SENSORS,
        killswitch_getter=lambda: False,
    )
    defaults.update(kwargs)
    return HealthCheckRuntime(**defaults)


@patch("gcm.health_checks.check_utils.runtime.get_derived_cluster", return_value="derived_test")
@patch("gcm.health_checks.check_utils.runtime.gni_lib")
@patch("gcm.health_checks.check_utils.runtime.init_logger")
@patch("gcm.health_checks.check_utils.runtime.socket")
def test_enter_initializes_fields(
    mock_socket: MagicMock,
    mock_init_logger: MagicMock,
    mock_gni: MagicMock,
    mock_derived: MagicMock,
) -> None:
    """Verify __enter__ populates logger, node, gpu_node_id, and derived_cluster."""
    mock_socket.gethostname.return_value = "testnode01"
    test_logger = logging.getLogger("test")
    mock_init_logger.return_value = (test_logger, MagicMock())
    mock_gni.get_gpu_node_id.return_value = "gpu-0"

    rt = _make_runtime()
    with rt as runtime:
        assert runtime.node == "testnode01"
        assert runtime.logger is test_logger
        assert runtime.gpu_node_id == "gpu-0"
        assert runtime.derived_cluster == "derived_test"


@patch("gcm.health_checks.check_utils.runtime.get_derived_cluster", return_value="test_cluster")
@patch("gcm.health_checks.check_utils.runtime.gni_lib")
@patch("gcm.health_checks.check_utils.runtime.init_logger")
@patch("gcm.health_checks.check_utils.runtime.socket")
def test_killswitch_enabled_exits_ok(
    mock_socket: MagicMock,
    mock_init_logger: MagicMock,
    mock_gni: MagicMock,
    mock_derived: MagicMock,
) -> None:
    """When killswitch_getter returns True, sys.exit should be called with 0."""
    mock_socket.gethostname.return_value = "testnode01"
    mock_init_logger.return_value = (logging.getLogger("test"), MagicMock())
    mock_gni.get_gpu_node_id.return_value = "gpu-0"

    with pytest.raises(SystemExit) as exc_info:
        with _make_runtime(killswitch_getter=lambda: True):
            pytest.fail("With block body should not be reached when killswitch is enabled")

    assert exc_info.value.code == ExitCode.OK.value


@patch("gcm.health_checks.check_utils.runtime.get_derived_cluster", return_value="test_cluster")
@patch("gcm.health_checks.check_utils.runtime.gni_lib")
@patch("gcm.health_checks.check_utils.runtime.init_logger")
@patch("gcm.health_checks.check_utils.runtime.socket")
def test_killswitch_disabled_continues(
    mock_socket: MagicMock,
    mock_init_logger: MagicMock,
    mock_gni: MagicMock,
    mock_derived: MagicMock,
) -> None:
    """When killswitch_getter returns False, the with block body should execute normally."""
    mock_socket.gethostname.return_value = "testnode01"
    mock_init_logger.return_value = (logging.getLogger("test"), MagicMock())
    mock_gni.get_gpu_node_id.return_value = "gpu-0"

    body_executed = False
    with _make_runtime(killswitch_getter=lambda: False) as rt:
        body_executed = True
        rt.exit_code = ExitCode.OK
        rt.msg = "all good"

    assert body_executed


@patch("gcm.health_checks.check_utils.runtime.get_derived_cluster", return_value="test_cluster")
@patch("gcm.health_checks.check_utils.runtime.gni_lib")
@patch("gcm.health_checks.check_utils.runtime.init_logger")
@patch("gcm.health_checks.check_utils.runtime.socket")
def test_finish_sets_code_and_exits(
    mock_socket: MagicMock,
    mock_init_logger: MagicMock,
    mock_gni: MagicMock,
    mock_derived: MagicMock,
) -> None:
    """finish() should set exit_code and msg, then call sys.exit with the code value."""
    mock_socket.gethostname.return_value = "testnode01"
    mock_init_logger.return_value = (logging.getLogger("test"), MagicMock())
    mock_gni.get_gpu_node_id.return_value = "gpu-0"

    with pytest.raises(SystemExit) as exc_info:
        with _make_runtime() as rt:
            rt.finish(ExitCode.CRITICAL, "something broke")

    assert exc_info.value.code == ExitCode.CRITICAL.value
    assert rt.exit_code == ExitCode.CRITICAL
    assert rt.msg == "something broke"


@patch("gcm.health_checks.check_utils.runtime.OutputContext")
@patch("gcm.health_checks.check_utils.runtime.TelemetryContext")
@patch("gcm.health_checks.check_utils.runtime.get_derived_cluster", return_value="test_cluster")
@patch("gcm.health_checks.check_utils.runtime.gni_lib")
@patch("gcm.health_checks.check_utils.runtime.init_logger")
@patch("gcm.health_checks.check_utils.runtime.socket")
def test_telemetry_and_output_contexts_entered(
    mock_socket: MagicMock,
    mock_init_logger: MagicMock,
    mock_gni: MagicMock,
    mock_derived: MagicMock,
    mock_telemetry_cls: MagicMock,
    mock_output_cls: MagicMock,
) -> None:
    """Both TelemetryContext and OutputContext should be entered during __enter__."""
    mock_socket.gethostname.return_value = "testnode01"
    mock_init_logger.return_value = (logging.getLogger("test"), MagicMock())
    mock_gni.get_gpu_node_id.return_value = "gpu-0"

    mock_telem_instance = MagicMock()
    mock_telemetry_cls.return_value = mock_telem_instance
    mock_output_instance = MagicMock()
    mock_output_cls.return_value = mock_output_instance

    with _make_runtime() as rt:
        rt.exit_code = ExitCode.OK

    mock_telem_instance.__enter__.assert_called_once()
    mock_output_instance.__enter__.assert_called_once()


@patch("gcm.health_checks.check_utils.runtime.get_derived_cluster", return_value="test_cluster")
@patch("gcm.health_checks.check_utils.runtime.gni_lib")
@patch("gcm.health_checks.check_utils.runtime.init_logger")
@patch("gcm.health_checks.check_utils.runtime.socket")
def test_gpu_node_id_failure_handled(
    mock_socket: MagicMock,
    mock_init_logger: MagicMock,
    mock_gni: MagicMock,
    mock_derived: MagicMock,
) -> None:
    """When gni_lib.get_gpu_node_id raises, gpu_node_id should be None and a warning logged."""
    mock_socket.gethostname.return_value = "testnode01"
    test_logger = logging.getLogger("test_gpu_failure")
    mock_init_logger.return_value = (test_logger, MagicMock())
    mock_gni.get_gpu_node_id.side_effect = RuntimeError("not a GPU host")

    with _make_runtime() as rt:
        assert rt.gpu_node_id is None
        rt.exit_code = ExitCode.OK
