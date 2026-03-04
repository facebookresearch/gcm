# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Structured telemetry export (JSON/CSV) for offline analysis."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import cast, Literal, TYPE_CHECKING

from gcm.exporters import register

if TYPE_CHECKING:
    from _typeshed import DataclassInstance
from gcm.monitoring.dataclass_utils import remove_none_dict_factory
from gcm.monitoring.sink.protocol import SinkAdditionalParams
from gcm.schemas.log import Log


def _snapshot(ts: int, msg: object) -> dict:
    d = asdict(
        cast("DataclassInstance", msg),
        dict_factory=remove_none_dict_factory,
    )
    d["timestamp"] = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")
    return d


@register("telemetry")
class Telemetry:
    """Append telemetry snapshots to a file in JSON or CSV format."""

    def __init__(
        self,
        *,
        file_path: str,
        format: Literal["json", "csv"] = "json",
    ) -> None:
        self.file_path = file_path
        self.format = format
        self._header_written = False

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        records = [_snapshot(data.ts, m) for m in data.message]
        if not records:
            return
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        with open(self.file_path, "a") as f:
            if self.format == "json":
                for r in records:
                    f.write(json.dumps(r) + "\n")
            else:
                all_keys = ["timestamp"] + sorted(
                    {k for r in records for k in r.keys()} - {"timestamp"}
                )
                w = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
                if not self._header_written:
                    w.writeheader()
                    self._header_written = True
                w.writerows(records)
