# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import csv
import json
import os
from dataclasses import asdict
from pathlib import Path

from gcm.exporters import register
from gcm.monitoring.sink.protocol import SinkAdditionalParams
from gcm.schemas.log import Log

_SUPPORTED_FORMATS = ("json", "csv")


@register("telemetry")
class Telemetry:
    """Append structured telemetry snapshots to a local file (NDJSON or CSV)."""

    def __init__(
        self,
        *,
        file_path: str,
        format: str = "json",
    ) -> None:
        if format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format {format!r}. Choose from: {_SUPPORTED_FORMATS}"
            )
        self._file_path = file_path
        self._format = format
        # Track whether a CSV header has been written in this session.
        # If the file already exists we skip the header so appended runs stay
        # parseable without a duplicate header row.
        self._csv_header_written = (
            os.path.isfile(file_path) and os.path.getsize(file_path) > 0
        )
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        rows = [asdict(msg) for msg in data.message]
        if not rows:
            return

        with open(self._file_path, "a") as fh:
            if self._format == "json":
                for row in rows:
                    fh.write(json.dumps(row) + "\n")
            else:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                if not self._csv_header_written:
                    writer.writeheader()
                    self._csv_header_written = True
                writer.writerows(rows)

    def shutdown(self) -> None:
        pass
