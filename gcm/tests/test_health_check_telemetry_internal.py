# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import sys
from typing import Callable, Dict, final, Iterable, Optional
from unittest.mock import MagicMock

import click
import pytest
from click import Path
from click.testing import CliRunner
from gcm.exporters.graph_api import GraphAPI
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.types import ExitCode
from gcm.monitoring.meta_utils.scribe import ScribeConfig, write_messages
from gcm.monitoring.meta_utils.scuba import ScubaMessage
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory, make_register, Register
from gcm.monitoring.utils.monitor import init_logger

from gcm.schemas.health_check.health_check_name import HealthCheckName
from gcm.schemas.health_check.log import HealthCheckLog
from gcm.schemas.log import Log
from gcm.tests.config import Config


def test_push_to_scribe(config: Config) -> None:
    log = HealthCheckLog(
        result=0,
        node="node0102",
        cluster="fair_cluster",
        derived_cluster="fair_cluster",
        health_check="xid errors",
        type="nagios",
        gpu_node_id="node_id",
        _msg=None,
        job_id=123,
        start_time=0,
        end_time=10,
    )

    stub_writer = MagicMock()
    graph_api_obj = GraphAPI(
        app_secret=config.graph_api_access_token,
        scribe_category="perfpipe_gcm_githubci",
        scribe_write=stub_writer,
    )
    graph_api_obj.write(
        data=Log(
            ts=123,
            message=[log],
        ),
        additional_params=SinkAdditionalParams(data_type=DataType.LOG),
    )
    stub_writer.assert_called_once()


ScribeWriter = Callable[
    [str, Iterable[ScubaMessage], ScribeConfig, Optional[int]], None
]


fake_registry: Dict[str, Factory[SinkImpl]] = {}
fake_register: Register[SinkImpl] = make_register(fake_registry)


@fake_register("graph_api")
@final
class FakeHealthCheckGraphAPI(SinkImpl):
    def __init__(
        self,
        app_secret: str,
        scribe_category: str = "test_cluster_health",
        scribe_write: ScribeWriter = write_messages,
    ) -> None:
        pass

    def write(self, data: Log, additional_params: SinkAdditionalParams) -> None:
        raise RuntimeError("Mocked error")


def test_telemetry_exception_not_affecting_check_output(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    @click.command()
    def main() -> None:
        exit_code = ExitCode.OK
        msg = "Success"

        logger, _ = init_logger(
            logger_name="nagios",
            log_dir=os.path.join(str(tmp_path), "nagios_logs"),
            log_name="test_node.log",
            log_level=getattr(logging, "INFO"),
        )
        with TelemetryContext(
            sink="graph_api",
            sink_opts=(
                "app_secret=13|7",
                "scribe_category=test_cluster_health",
            ),
            logger=logger,
            cluster="fair_cluster",
            derived_cluster="fair_cluster",
            type="nagios",
            name=HealthCheckName.IPMI_SEL.value,
            node="test_node",
            get_exit_code_msg=lambda: (exit_code, msg),
            gpu_node_id="abcd",
            job_id=14,
            telem_registry=fake_registry,
        ):
            sys.exit(exit_code.value)

    caplog.at_level(logging.INFO)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, "", catch_exceptions=False)

    assert result.exit_code == 0
    assert "Telemetry failed with exception" in caplog.text
