# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from gcm.exporters.telemetry import Telemetry
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.log import Log


@dataclass
class GpuSnapshot:
    hostname: str
    gpu_id: int
    gpu_util: int
    mem_used_percent: int


_PARAMS = SinkAdditionalParams(data_type=DataType.METRIC)


class TestTelemetryExporterJSON:
    def test_single_write_produces_ndjson_line(self, tmp_path: Path) -> None:
        out = tmp_path / "telemetry.json"
        sink = Telemetry(file_path=str(out))

        sink.write(
            Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]),
            _PARAMS,
        )

        lines = out.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0]) == {
            "hostname": "node-1",
            "gpu_id": 0,
            "gpu_util": 88,
            "mem_used_percent": 71,
        }

    def test_multiple_writes_append(self, tmp_path: Path) -> None:
        out = tmp_path / "telemetry.json"
        sink = Telemetry(file_path=str(out))

        sink.write(Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]), _PARAMS)
        sink.write(Log(ts=1, message=[GpuSnapshot("node-1", 1, 42, 50)]), _PARAMS)

        lines = out.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["gpu_id"] == 1

    def test_empty_message_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "telemetry.json"
        sink = Telemetry(file_path=str(out))

        sink.write(Log(ts=0, message=[]), _PARAMS)

        assert not out.exists() or out.read_text() == ""

    def test_cross_session_append_no_duplicate_content(self, tmp_path: Path) -> None:
        """Re-opening the same file in a new Telemetry instance should append, not overwrite."""
        out = tmp_path / "telemetry.json"

        Telemetry(file_path=str(out)).write(
            Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]), _PARAMS
        )
        Telemetry(file_path=str(out)).write(
            Log(ts=1, message=[GpuSnapshot("node-1", 1, 42, 50)]), _PARAMS
        )

        lines = out.read_text().splitlines()
        assert len(lines) == 2


class TestTelemetryExporterCSV:
    def test_csv_write_includes_header_and_row(self, tmp_path: Path) -> None:
        out = tmp_path / "telemetry.csv"
        sink = Telemetry(file_path=str(out), format="csv")

        sink.write(
            Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]),
            _PARAMS,
        )

        reader = list(csv.DictReader(out.open()))
        assert len(reader) == 1
        assert reader[0]["hostname"] == "node-1"
        assert reader[0]["gpu_util"] == "88"

    def test_csv_header_not_repeated_within_session(self, tmp_path: Path) -> None:
        out = tmp_path / "telemetry.csv"
        sink = Telemetry(file_path=str(out), format="csv")

        sink.write(Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]), _PARAMS)
        sink.write(Log(ts=1, message=[GpuSnapshot("node-1", 1, 42, 50)]), _PARAMS)

        rows = list(csv.DictReader(out.open()))
        assert len(rows) == 2

    def test_csv_header_not_repeated_across_sessions(self, tmp_path: Path) -> None:
        """Second Telemetry instance for an existing non-empty file must not re-write header."""
        out = tmp_path / "telemetry.csv"

        Telemetry(file_path=str(out), format="csv").write(
            Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]), _PARAMS
        )
        Telemetry(file_path=str(out), format="csv").write(
            Log(ts=1, message=[GpuSnapshot("node-1", 1, 42, 50)]), _PARAMS
        )

        rows = list(csv.DictReader(out.open()))
        assert len(rows) == 2  # only 2 data rows, no duplicate header row


class TestTelemetryExporterValidation:
    def test_missing_file_path_raises(self) -> None:
        with pytest.raises(TypeError):
            Telemetry()  # type: ignore[call-arg]

    def test_invalid_format_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported format"):
            Telemetry(file_path=str(tmp_path / "out.txt"), format="xml")

    def test_auto_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "a" / "b" / "c" / "telemetry.json"
        sink = Telemetry(file_path=str(out))

        sink.write(Log(ts=0, message=[GpuSnapshot("node-1", 0, 88, 71)]), _PARAMS)

        assert out.exists()
