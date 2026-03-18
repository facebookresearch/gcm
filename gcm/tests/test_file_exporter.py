# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from gcm.exporters.file import File
from gcm.monitoring.sink.protocol import DataIdentifier, SinkAdditionalParams
from gcm.schemas.log import Log


@dataclass
class SamplePayload:
    job_id: int
    state: str
    user: str


@dataclass
class OtherSamplePayload:
    gpu_uuid: str
    memory_used_mb: int


def test_file_exporter_csv(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    sink = File(file_path=str(path), format="csv")
    sink.write(
        Log(ts=1000, message=[SamplePayload(job_id=1, state="RUNNING", user="alice")]),
        SinkAdditionalParams(data_identifier=DataIdentifier.GENERIC),
    )
    sink.write(
        Log(ts=2000, message=[SamplePayload(job_id=2, state="PENDING", user="bob")]),
        SinkAdditionalParams(data_identifier=DataIdentifier.GENERIC),
    )
    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["state"] == "RUNNING"
    assert rows[0]["user"] == "alice"
    assert rows[1]["state"] == "PENDING"
    assert rows[1]["user"] == "bob"


def test_file_exporter_csv_rolls_over_on_schema_change(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    sink = File(file_path=str(path), format="csv")

    sink.write(
        Log(ts=1000, message=[SamplePayload(job_id=1, state="RUNNING", user="alice")]),
        SinkAdditionalParams(data_identifier=DataIdentifier.GENERIC),
    )
    sink.write(
        Log(
            ts=2000,
            message=[OtherSamplePayload(gpu_uuid="GPU-123", memory_used_mb=2048)],
        ),
        SinkAdditionalParams(data_identifier=DataIdentifier.GENERIC),
    )

    lines = path.read_text().splitlines()
    assert lines == [
        "job_id,state,user",
        "1,RUNNING,alice",
    ]

    path_rollover = tmp_path / "data_1.csv"
    rollover_lines = path_rollover.read_text().splitlines()
    assert rollover_lines == [
        "gpu_uuid,memory_used_mb",
        "GPU-123,2048",
    ]


def test_file_exporter_csv_resumes_without_duplicate_header(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"

    # First process run
    sink1 = File(file_path=str(path), format="csv")
    sink1.write(
        Log(ts=1000, message=[SamplePayload(job_id=1, state="RUNNING", user="alice")]),
        SinkAdditionalParams(data_identifier=DataIdentifier.GENERIC),
    )

    # Clean up logger handlers to simulate proper process termination/restart
    # The logger name is constructed in _file.py as __name__ + file_path
    # This ensures we don't get duplicate logging handlers which would duplicate row output
    logger_name = "gcm.exporters.file" + str(path)
    logger = logging.getLogger(logger_name)
    logger.handlers = []

    # Second process run
    sink2 = File(file_path=str(path), format="csv")
    sink2.write(
        Log(ts=2000, message=[SamplePayload(job_id=2, state="PENDING", user="bob")]),
        SinkAdditionalParams(data_identifier=DataIdentifier.GENERIC),
    )

    lines = path.read_text().splitlines()
    assert lines == [
        "job_id,state,user",
        "1,RUNNING,alice",
        "2,PENDING,bob",
    ]
