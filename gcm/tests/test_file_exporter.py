# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import csv
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
    assert rows[0]["normal.state"] == "RUNNING"
    assert rows[0]["normal.user"] == "alice"
    assert rows[1]["normal.state"] == "PENDING"
    assert rows[1]["normal.user"] == "bob"
