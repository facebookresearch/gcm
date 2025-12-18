# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from typing import List
from unittest.mock import create_autospec, MagicMock

import pytest
from gcm.exporters.graph_api import GraphAPI, ScribeWrite
from gcm.exporters.stdout import Stdout

from gcm.monitoring.clock import ClockImpl
from gcm.monitoring.meta_utils.scribe import ScribeLog
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log
from gcm.schemas.slurm.sacct import SacctPayload

TEST_TIME = ClockImpl().unixtime()


class TestStdout:
    @staticmethod
    @pytest.mark.parametrize(
        "logs, expected",
        [
            (
                Log(
                    ts=TEST_TIME,
                    message=[],
                ),
                [],
            ),
            (
                Log(
                    ts=TEST_TIME,
                    message=[
                        SacctPayload(
                            time=TEST_TIME,
                            end_ds="2022-08-24",
                            cluster="cluster_name",
                            sacct={"foo": "bar"},
                        )
                    ],
                ),
                [
                    {
                        "time": TEST_TIME,
                        "cluster": "cluster_name",
                        "end_ds": "2022-08-24",
                        "sacct": {"foo": "bar"},
                    }
                ],
            ),
            (
                Log(
                    ts=TEST_TIME,
                    message=[
                        SacctPayload(
                            time=TEST_TIME,
                            end_ds="2022-08-24",
                            cluster="cluster_name",
                            sacct={"foo": "bar"},
                        ),
                        SacctPayload(
                            time=TEST_TIME,
                            end_ds="2022-08-24",
                            cluster="cluster_name",
                            sacct={"foo": "quux"},
                        ),
                    ],
                ),
                [
                    {
                        "time": TEST_TIME,
                        "cluster": "cluster_name",
                        "end_ds": "2022-08-24",
                        "sacct": {"foo": "bar"},
                    },
                    {
                        "time": TEST_TIME,
                        "cluster": "cluster_name",
                        "end_ds": "2022-08-24",
                        "sacct": {"foo": "quux"},
                    },
                ],
            ),
        ],
    )
    def test_prints_json(
        capsys: pytest.CaptureFixture,
        logs: Log,
        expected: List[ScribeLog],
    ) -> None:
        sink = Stdout()

        sink.write(
            data=logs, additional_params=SinkAdditionalParams(data_type=DataType.LOG)
        )

        assert json.loads(capsys.readouterr().out) == expected


class StubScribeWrite(MagicMock, ScribeWrite):
    pass


@pytest.fixture
def stub_scribe_write() -> StubScribeWrite:
    return create_autospec(ScribeWrite, instance=True)


class TestGraphAPI:
    @staticmethod
    def test_propagates_other_exceptions(stub_scribe_write: StubScribeWrite) -> None:
        class CustomException(Exception):
            pass

        stub_scribe_write.side_effect = CustomException()
        sink = GraphAPI(
            app_secret="app_id|secret",
            scribe_category="test",
            scribe_write=stub_scribe_write,
        )

        with pytest.raises(CustomException):
            sink.write(
                data=Log(
                    ts=TEST_TIME,
                    message=[
                        SacctPayload(
                            time=TEST_TIME,
                            end_ds="2022-08-24",
                            cluster="cluster_name",
                            sacct={"foo": "bar"},
                        )
                    ],
                ),
                additional_params=SinkAdditionalParams(data_type=DataType.LOG),
            )
