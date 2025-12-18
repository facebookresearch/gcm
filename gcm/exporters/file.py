# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import os
from dataclasses import asdict
from typing import Callable, Optional, Tuple

from gcm.exporters import register

from gcm.monitoring.meta_utils.scuba import to_scuba_message
from gcm.monitoring.sink.protocol import DataIdentifier, SinkAdditionalParams

from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.log import Log

split_path: Callable[[str], Tuple[str, str]] = lambda path: (
    os.path.dirname(path),
    os.path.basename(path),
)


@register("file")
class File:
    """Write data to file."""

    def __init__(
        self,
        *,
        file_path: Optional[str] = None,
        job_file_path: Optional[str] = None,
        node_file_path: Optional[str] = None,
    ):
        if all(path is None for path in [file_path, job_file_path, node_file_path]):
            raise Exception(
                "When using the file sink at least one file_path needs to be specified. See gcm %collector% --help"
            )

        self.data_identifier_to_logger_map = {}

        if file_path is not None:
            file_directory, file_name = split_path(file_path)
            self.data_identifier_to_logger_map[DataIdentifier.GENERIC], _ = init_logger(
                logger_name=__name__ + file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )

        if job_file_path is not None:
            file_directory, file_name = split_path(job_file_path)
            self.data_identifier_to_logger_map[DataIdentifier.JOB], _ = init_logger(
                logger_name=__name__ + job_file_path,
                log_dir=file_directory,
                log_name=file_name,
                log_formatter=None,
            )

        if node_file_path is not None:
            file_directory, file_name = split_path(node_file_path)
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

        # update file path if data_identifier is present on additional_params
        if additional_params.data_identifier:
            data_identifier = additional_params.data_identifier
            if data_identifier not in self.data_identifier_to_logger_map:
                raise AssertionError(
                    f"data_identifier value is unsupported on file sink: {data_identifier}"
                )
            if self.data_identifier_to_logger_map[data_identifier] is None:
                raise AssertionError(
                    f"The sink is missing a required param for the following data_identifier: {data_identifier}. See gcm %collector% --help"
                )
            logger = self.data_identifier_to_logger_map[data_identifier]
        else:
            logger = self.data_identifier_to_logger_map[DataIdentifier.GENERIC]

        for payload in data.message:
            # TODO: remove to_scuba_message once slurm_job_monitor migrates to OpenTelemetry exporter
            logger.info(json.dumps(asdict(to_scuba_message(payload))))
