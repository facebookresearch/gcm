# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import socket
from typing import Iterable, Optional, Protocol

from gcm.exporters import register

from gcm.monitoring.clock import Clock, ClockImpl
from gcm.monitoring.decorators import Retry
from gcm.monitoring.meta_utils.ods import get_ods_data, ODSConfig, write
from gcm.monitoring.meta_utils.scribe import ScribeConfig, ScribeError, write_messages
from gcm.monitoring.meta_utils.scuba import ScubaMessage, to_scuba_message
from gcm.monitoring.sink.protocol import DataIdentifier, DataType, SinkAdditionalParams
from gcm.schemas.log import Log
from requests.exceptions import RequestException

from typing_extensions import Never


logger = logging.getLogger(__name__)


def get_graph_api_token() -> str:
    if "GRAPH_API_ACCESS_TOKEN" not in os.environ:
        raise ValueError(
            "could not find a graph api access token, you can set the environment variable GRAPH_API_ACCESS_TOKEN."
        )
    return os.environ["GRAPH_API_ACCESS_TOKEN"]


class ScribeWrite(Protocol):
    def __call__(
        self,
        category: str,
        messages: Iterable[ScubaMessage],
        config: ScribeConfig,
        timestamp: Optional[int] = None,
        timeout: int = 60,
        clock: Clock = ClockImpl(),
    ) -> None: ...


@register("graph_api")
class GraphAPI:
    """Write formatted logs to ODS/Scribe via Graph API"""

    def __init__(
        self,
        *,
        # T173219192: remove app_id
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        scribe_category: Optional[str] = None,
        node_scribe_category: Optional[str] = None,
        job_scribe_category: Optional[str] = None,
        statvfs_scribe_category: Optional[str] = None,
        pure_scribe_category: Optional[str] = None,
        ods_entity: Optional[str | int] = None,
        scribe_write: ScribeWrite = write_messages,
    ):
        self._scribe_category = scribe_category
        self.data_identifier_to_scribe_map = {
            DataIdentifier.JOB: job_scribe_category,
            DataIdentifier.NODE: node_scribe_category,
            DataIdentifier.STATVFS: statvfs_scribe_category,
            DataIdentifier.PURE: pure_scribe_category,
        }
        self.scribe_write = scribe_write
        if ods_entity is None:
            self._ods_entity = socket.gethostname()
        else:
            self._ods_entity = str(ods_entity)
        token = app_secret
        if app_secret is None:
            token = get_graph_api_token()
            self.__scribe_config = ScribeConfig(secret_key=token)
            self.__ods_config = ODSConfig(secret_key=token)
        else:
            if app_id is not None:
                # Create the ScribeConfig to read secret key from file
                self.__scribe_config = ScribeConfig(secret_key=app_secret)
                # Concat app_id and secret_key to maintain backwards compatibility in case both app_id and secret_key are provided
                token = f"{app_id}|{self.__scribe_config.secret_key}"
                self.__scribe_config.secret_key = token
                self.__ods_config = ODSConfig(secret_key=token)
            else:
                assert (
                    token is not None
                ), "graph_api exporter requires app_secret to be provided: -o app_secret='<id>|<secret_key>'"
                self.__scribe_config = ScribeConfig(secret_key=token)
                self.__ods_config = ODSConfig(secret_key=token)

    def assert_never(self, x: Never) -> Never:
        raise AssertionError(f"Unhandled type: {type(x).__name__}")

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        """Exports data to Graph API calling different implementations based on data type."""
        if additional_params.data_type:
            if additional_params.data_type is DataType.LOG:
                return self._write_log(data, additional_params)
            elif additional_params.data_type is DataType.METRIC:
                return self._write_metric(
                    data,
                    heterogeneous_cluster_v1=additional_params.heterogeneous_cluster_v1,
                )
            else:
                logger.error(
                    f"We expected scuba or ods, but got {additional_params.data_type}"
                )
                self.assert_never(additional_params.data_type)
        else:
            logger.error(
                f"Graph API writes requires data_type to be specified: {additional_params}"
            )
            return

    def _write_metric(self, data: Log, heterogeneous_cluster_v1: bool) -> None:
        """Receives a list of device and host metrics, convert it to ODSData and sends to ODS as a single request.

        Batching the request here is benefitial because instead of sending 1 req per GPU (~8 per host), we will send 1 per host.
        """

        ods_data = []
        for message in data.message:
            entity = self._ods_entity
            if hasattr(message, "derived_cluster"):
                if "." in message.derived_cluster:
                    partition = message.derived_cluster.split(".")[1]
                    entity = f"{self._ods_entity}.{partition}"
            ods_data.append(
                get_ods_data(
                    entity=entity,
                    data=message,
                    unixtime=data.ts,
                )
            )
        write(ods_data, self.__ods_config)

    def _write_log(self, data: Log, additional_params: SinkAdditionalParams) -> None:
        category = self._scribe_category

        # update scribe category if data_identifier is present on additional_params
        if additional_params.data_identifier:
            data_identifier = additional_params.data_identifier
            if data_identifier not in self.data_identifier_to_scribe_map:
                raise AssertionError(
                    f"data_type value is unsupported on graph_api sink: {data_identifier}"
                )
            category = self.data_identifier_to_scribe_map[data_identifier]

        assert category is not None, "scribe_category argument is missing"
        # converting messages to ScubaMessage before sending them through GraphAPI:
        # https://www.internalfb.com/intern/wiki/Scuba/Quick_Start_Guide/Data_Types/
        scribe_messages = list(map(to_scuba_message, data.message))
        for scribe_category in category.split(","):
            try:
                self.scribe_write(
                    scribe_category,
                    scribe_messages,
                    config=self.__scribe_config,
                    timestamp=data.ts,
                )
            except (RequestException, ScribeError) as e:
                raise Retry() from e
