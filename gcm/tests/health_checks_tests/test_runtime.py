# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for the HealthCheckRuntime context manager."""

import logging
from typing import Callable, Optional
from unittest.mock import MagicMock

import pytest
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.types import ExitCode
from gcm.schemas.health_check.health_check_name import HealthCheckName


def _fake_init_logger(
    logger_name: str, log_dir: str, log_name: str, log_level: int
) -> tuple:
    return (logging.getLogger("test"), MagicMock())


def _fake_get_derived_cluster(
    cluster: str, heterogeneous_cluster_v1: bool, data: dict
) -> str:
    return "derived_test"


def _make_runtime(
    killswitch_getter: Callable[[], bool] = lambda: False,
    get_hostname: Callable[[], str] = lambda: "testnode01",
    get_gpu_node_id: Callable[[], Optional[str]] = lambda: "gpu-0",
    init_logger: Callable = _fake_init_logger,
    get_derived_cluster: Callable = _fake_get_derived_cluster,
    telemetry_context_factory: Optional[Callable] = None,
    output_context_factory: Optional[Callable] = None,
) -> HealthCheckRuntime:
    rt = HealthCheckRuntime(
        cluster="test_cluster",
        check_type="prolog",
        log_level="INFO",
        log_folder="/tmp",
        sink="do_nothing",
        sink_opts=(),
        verbose_out=False,
        heterogeneous_cluster_v1=False,
        health_check_name=HealthCheckName.CHECK_SENSORS,
        killswitch_getter=killswitch_getter,
        get_hostname=get_hostname,
        get_gpu_node_id=get_gpu_node_id,
        init_logger=init_logger,
        get_derived_cluster=get_derived_cluster,
    )
    if telemetry_context_factory is not None:
        rt.telemetry_context_factory = telemetry_context_factory
    if output_context_factory is not None:
        rt.output_context_factory = output_context_factory
    return rt


def test_enter_initializes_fields() -> None:
    """Verify __enter__ populates logger, node, gpu_node_id, and derived_cluster."""
    with _make_runtime() as rt:
        assert rt.node == "testnode01"
        assert rt.logger is not None
        assert rt.gpu_node_id == "gpu-0"
        assert rt.derived_cluster == "derived_test"


def test_killswitch_enabled_exits_ok() -> None:
    """When killswitch_getter returns True, sys.exit(0) is raised and msg is set."""
    with pytest.raises(SystemExit) as exc_info:
        with _make_runtime(killswitch_getter=lambda: True):
            pytest.fail(
                "With block body should not be reached when killswitch is enabled"
            )

    assert exc_info.value.code == ExitCode.OK.value


def test_killswitch_cleans_up_contexts() -> None:
    """When killswitch fires, both contexts must be entered and exited."""
    mock_telem_cls = MagicMock()
    mock_telem_instance = MagicMock()
    mock_telem_cls.return_value = mock_telem_instance

    mock_output_cls = MagicMock()
    mock_output_instance = MagicMock()
    mock_output_cls.return_value = mock_output_instance

    with pytest.raises(SystemExit):
        with _make_runtime(
            killswitch_getter=lambda: True,
            telemetry_context_factory=mock_telem_cls,
            output_context_factory=mock_output_cls,
        ):
            pass

    mock_telem_instance.__enter__.assert_called_once()
    mock_telem_instance.__exit__.assert_called_once()
    mock_output_instance.__enter__.assert_called_once()
    mock_output_instance.__exit__.assert_called_once()


def test_killswitch_sets_msg() -> None:
    """When killswitch fires, msg should be set for TelemetryContext/OutputContext."""
    rt = _make_runtime(killswitch_getter=lambda: True)
    with pytest.raises(SystemExit):
        rt.__enter__()

    assert rt.exit_code == ExitCode.OK
    assert rt.msg == f"{HealthCheckName.CHECK_SENSORS.value} is disabled by killswitch."


def test_killswitch_disabled_continues() -> None:
    """When killswitch_getter returns False, the with block body should execute normally."""
    body_executed = False
    with _make_runtime(killswitch_getter=lambda: False) as rt:
        body_executed = True
        rt.exit_code = ExitCode.OK
        rt.msg = "all good"

    assert body_executed


def test_finish_sets_code_and_exits() -> None:
    """finish() should set exit_code and msg, then call sys.exit with the code value."""
    with pytest.raises(SystemExit) as exc_info:
        with _make_runtime() as rt:
            rt.finish(ExitCode.CRITICAL, "something broke")

    assert exc_info.value.code == ExitCode.CRITICAL.value
    assert rt.exit_code == ExitCode.CRITICAL
    assert rt.msg == "something broke"


def test_telemetry_and_output_contexts_entered() -> None:
    """Both TelemetryContext and OutputContext should be entered during __enter__."""
    mock_telem_cls = MagicMock()
    mock_telem_instance = MagicMock()
    mock_telem_cls.return_value = mock_telem_instance

    mock_output_cls = MagicMock()
    mock_output_instance = MagicMock()
    mock_output_cls.return_value = mock_output_instance

    with _make_runtime(
        telemetry_context_factory=mock_telem_cls,
        output_context_factory=mock_output_cls,
    ) as rt:
        rt.exit_code = ExitCode.OK

    mock_telem_instance.__enter__.assert_called_once()
    mock_output_instance.__enter__.assert_called_once()


def test_gpu_node_id_failure_handled() -> None:
    """When get_gpu_node_id raises, gpu_node_id should be None."""

    def failing_gpu_node_id() -> str:
        raise RuntimeError("not a GPU host")

    with _make_runtime(get_gpu_node_id=failing_gpu_node_id) as rt:
        assert rt.gpu_node_id is None
        rt.exit_code = ExitCode.OK
