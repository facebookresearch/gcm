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


def _schema_versioned_path(path: str, schema_index: int) -> str:
    if schema_index == 0:
        return path
    stem, ext = os.path.splitext(path)
    return f"{stem}_{schema_index}{ext}"


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
        self._data_identifier_to_base_path: Dict[DataIdentifier, str] = {}
        if self.format == "csv":
            self._csv_fieldnames: Dict[str, Tuple[str, ...]] = {}
            self._csv_schema_index: Dict[DataIdentifier, int] = {}

        if file_path is not None:
            file_directory, file_name = split_path(file_path)
            self._data_identifier_to_path[DataIdentifier.GENERIC] = file_path
            self._data_identifier_to_base_path[DataIdentifier.GENERIC] = file_path
            if self.format == "csv":
                self._csv_schema_index[DataIdentifier.GENERIC] = 0
            self.data_identifier_to_logger_map[DataIdentifier.GENERIC], _ = init_logger(
                logger_name=__name__ + file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )
            if self.format == "csv":
                self._load_existing_header(file_path)

        if job_file_path is not None:
            file_directory, file_name = split_path(job_file_path)
            self._data_identifier_to_path[DataIdentifier.JOB] = job_file_path
            self._data_identifier_to_base_path[DataIdentifier.JOB] = job_file_path
            if self.format == "csv":
                self._csv_schema_index[DataIdentifier.JOB] = 0
            self.data_identifier_to_logger_map[DataIdentifier.JOB], _ = init_logger(
                logger_name=__name__ + job_file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )
            if self.format == "csv":
                self._load_existing_header(job_file_path)

        if node_file_path is not None:
            file_directory, file_name = split_path(node_file_path)
            self._data_identifier_to_path[DataIdentifier.NODE] = node_file_path
            self._data_identifier_to_base_path[DataIdentifier.NODE] = node_file_path
            if self.format == "csv":
                self._csv_schema_index[DataIdentifier.NODE] = 0
            self.data_identifier_to_logger_map[DataIdentifier.NODE], _ = init_logger(
                logger_name=__name__ + node_file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )
            if self.format == "csv":
                self._load_existing_header(node_file_path)

    def _load_existing_header(self, path: str) -> None:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return

        try:
            with open(path, newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    self._csv_fieldnames[path] = tuple(header)
        except Exception:
            pass

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
            fieldnames = tuple(all_keys)
            previous_fieldnames = self._csv_fieldnames.get(path)

            if (
                previous_fieldnames is not None
                and previous_fieldnames != fieldnames
                and data_identifier in self._csv_schema_index
            ):
                next_schema_index = self._csv_schema_index[data_identifier] + 1
                self._csv_schema_index[data_identifier] = next_schema_index

                base_path = self._data_identifier_to_base_path[data_identifier]
                path = _schema_versioned_path(base_path, next_schema_index)
                self._data_identifier_to_path[data_identifier] = path

                file_directory, file_name = split_path(path)
                logger, _ = init_logger(
                    logger_name=__name__ + path,
                    log_dir=file_directory,
                    log_name=file_name,
                    log_formatter=None,
                )
                self.data_identifier_to_logger_map[data_identifier] = logger
                previous_fieldnames = self._csv_fieldnames.get(path)

            if previous_fieldnames != fieldnames:
                header_buf = io.StringIO()
                header_writer = csv.DictWriter(
                    header_buf,
                    fieldnames=all_keys,
                    extrasaction="ignore",
                    lineterminator="",
                )
                header_writer.writeheader()
                logger.info(header_buf.getvalue())
                self._csv_fieldnames[path] = fieldnames

            row_buf = io.StringIO()
            row_writer = csv.DictWriter(
                row_buf,
                fieldnames=all_keys,
                extrasaction="ignore",
                lineterminator="",
            )
            for record in records:
                row_buf.seek(0)
                row_buf.truncate(0)
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
