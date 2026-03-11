# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import csv
import io
import json
import logging
import os
from dataclasses import asdict
from typing import Any, Callable, cast, Dict, Literal, Optional, Tuple, TYPE_CHECKING

from gcm.exporters import register
from gcm.monitoring.dataclass_utils import asdict_recursive
from gcm.monitoring.meta_utils.scuba import to_scuba_message
from gcm.monitoring.sink.protocol import DataIdentifier, SinkAdditionalParams
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.log import Log

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

split_path: Callable[[str], Tuple[str, str]] = lambda path: (
    os.path.dirname(path),
    os.path.basename(path),
)


def _flatten_for_csv(payload: object) -> Dict[str, Any]:
    """Flatten scuba message dict for CSV output."""
    flat = asdict_recursive(to_scuba_message(cast("DataclassInstance", payload)))
    return flat if isinstance(flat, dict) else {}


@register("file")
class File:
    """Write data to file."""

    def __init__(
        self,
        *,
        file_path: Optional[str] = None,
        job_file_path: Optional[str] = None,
        node_file_path: Optional[str] = None,
        format: Literal["json", "csv"] = "json",
    ):
        if all(path is None for path in [file_path, job_file_path, node_file_path]):
            raise Exception(
                "When using the file sink at least one file_path needs to be specified. See gcm %collector% --help"
            )

        self.format = format
        self.data_identifier_to_logger_map: Dict[
            DataIdentifier, Optional[logging.Logger]
        ] = {}
        self._data_identifier_to_path: Dict[DataIdentifier, str] = {}
        if self.format == "csv":
            self._csv_header_written: Dict[str, bool] = {}

        if file_path is not None:
            file_directory, file_name = split_path(file_path)
            self._data_identifier_to_path[DataIdentifier.GENERIC] = file_path
            self.data_identifier_to_logger_map[DataIdentifier.GENERIC], _ = init_logger(
                logger_name=__name__ + file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )

        if job_file_path is not None:
            file_directory, file_name = split_path(job_file_path)
            self._data_identifier_to_path[DataIdentifier.JOB] = job_file_path
            self.data_identifier_to_logger_map[DataIdentifier.JOB], _ = init_logger(
                logger_name=__name__ + job_file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )

        if node_file_path is not None:
            file_directory, file_name = split_path(node_file_path)
            self._data_identifier_to_path[DataIdentifier.NODE] = node_file_path
            self.data_identifier_to_logger_map[DataIdentifier.NODE], _ = init_logger(
                logger_name=__name__ + node_file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:

        data_identifier = additional_params.data_identifier or DataIdentifier.GENERIC
        if data_identifier not in self.data_identifier_to_logger_map:
            raise AssertionError(
                f"data_identifier value is unsupported on file sink: {data_identifier}"
            )
        if self.data_identifier_to_logger_map[data_identifier] is None:
            raise AssertionError(
                f"The sink is missing a required param for the following data_identifier: {data_identifier}. See gcm %collector% --help"
            )
        logger = self.data_identifier_to_logger_map[data_identifier]
        assert logger is not None

        if self.format == "csv":
            path = self._data_identifier_to_path.get(data_identifier)
            if path is None:
                raise AssertionError(
                    "CSV format requires data_identifier to match a configured path"
                )
            records = [_flatten_for_csv(p) for p in data.message]
            if not records:
                return
            all_keys = sorted({k for r in records for k in r.keys()})
            header_done = self._csv_header_written.get(path, False)

            if not header_done:
                header_buf = io.StringIO()
                header_writer = csv.DictWriter(
                    header_buf,
                    fieldnames=all_keys,
                    extrasaction="ignore",
                    lineterminator="",
                )
                header_writer.writeheader()
                logger.info(header_buf.getvalue())
                self._csv_header_written[path] = True

            for record in records:
                row_buf = io.StringIO()
                row_writer = csv.DictWriter(
                    row_buf,
                    fieldnames=all_keys,
                    extrasaction="ignore",
                    lineterminator="",
                )
                row_writer.writerow(record)
                logger.info(row_buf.getvalue())
        elif self.format == "json":
            for payload in data.message:
                # TODO: remove to_scuba_message once slurm_job_monitor migrates to OpenTelemetry exporter
                logger.info(json.dumps(asdict(to_scuba_message(payload))))
        else:
            raise ValueError(f"Unsupported format: {self.format!r}")

    def shutdown(self) -> None:
        pass
