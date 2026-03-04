# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import csv
import json

from gcm.exporters.telemetry import Telemetry
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.device_metrics import DevicePlusJobMetrics
from gcm.schemas.log import Log


def test_telemetry_json(tmp_path) -> None:
    path = tmp_path / "telemetry.json"
    sink = Telemetry(file_path=str(path), format="json")
    msg = DevicePlusJobMetrics(
        gpu_id=3,
        hostname="node-42",
        job_id=91283,
        job_user="research_team",
        gpu_util=88,
        mem_used_percent=90,
        temperature=78,
        power_draw=310,
        retired_pages_count_single_bit=0,
        retired_pages_count_double_bit=0,
    )
    sink.write(
        Log(ts=1741114282, message=[msg]),
        SinkAdditionalParams(data_type=DataType.LOG),
    )
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["timestamp"] == "2025-03-04T18:51:22"  # UTC for ts=1741114282
    assert data["hostname"] == "node-42"
    assert data["gpu_id"] == 3
    assert data["job_id"] == 91283
    assert data["job_user"] == "research_team"
    assert data["gpu_util"] == 88
    assert data["temperature"] == 78
    assert data["power_draw"] == 310


def test_telemetry_csv(tmp_path) -> None:
    path = tmp_path / "telemetry.csv"
    sink = Telemetry(file_path=str(path), format="csv")
    msg = DevicePlusJobMetrics(
        gpu_id=0,
        hostname="node-1",
        job_id=100,
        job_user="user",
        gpu_util=50,
        temperature=65,
        power_draw=200,
    )
    sink.write(
        Log(ts=1741114282, message=[msg]),
        SinkAdditionalParams(data_type=DataType.LOG),
    )
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2025-03-04T18:51:22"  # UTC for ts=1741114282
    assert rows[0]["hostname"] == "node-1"
    assert rows[0]["gpu_id"] == "0"
    assert rows[0]["gpu_util"] == "50"


def test_telemetry_csv_append(tmp_path) -> None:
    path = tmp_path / "telemetry.csv"
    sink = Telemetry(file_path=str(path), format="csv")
    msg = DevicePlusJobMetrics(gpu_id=0, hostname="n1", gpu_util=10)
    sink.write(Log(ts=1000, message=[msg]), SinkAdditionalParams(data_type=DataType.LOG))
    sink.write(Log(ts=2000, message=[msg]), SinkAdditionalParams(data_type=DataType.LOG))
    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["timestamp"] == "1970-01-01T00:16:40"
    assert rows[1]["timestamp"] == "1970-01-01T00:33:20"
