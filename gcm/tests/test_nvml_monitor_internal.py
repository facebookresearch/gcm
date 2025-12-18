# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import List

from gcm.exporters.graph_api import GraphAPI

from gcm.monitoring.clock import ClockImpl
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams
from gcm.schemas.device_metrics import DevicePlusJobMetrics
from gcm.schemas.host_metrics import HostMetrics
from gcm.schemas.indexed_device_metrics import IndexedDeviceMetrics
from gcm.schemas.log import Log
from gcm.tests.config import Config
from gcm.tests.conftest import report_url

TEST_TIME = ClockImpl().unixtime()

ODS_METRICS: List[IndexedDeviceMetrics | HostMetrics] = list(
    [
        IndexedDeviceMetrics(
            gpu_index=1,
            mem_util=15,
            mem_used_percent=55,
            gpu_util=7,
            temperature=77,
            power_draw=35,
            power_used_percent=20,
            retired_pages_count_single_bit=10,
            retired_pages_count_double_bit=11,
        ),
        IndexedDeviceMetrics(
            gpu_index=2,
            mem_util=10,
            mem_used_percent=50,
            gpu_util=10,
            temperature=57,
            power_draw=10,
            power_used_percent=20,
            retired_pages_count_single_bit=0,
            retired_pages_count_double_bit=1,
        ),
        HostMetrics(
            max_gpu_util=55,
            min_gpu_util=32,
            avg_gpu_util=40.76,
            ram_util=88.77,
        ),
    ]
)

SCRIBE_METRIC = DevicePlusJobMetrics(
    gpu_id=1,
    hostname="devv",
    job_id=10,
    job_user="luccab",
    job_gpus="0,1",
    job_num_gpus=2,
    job_num_cpus=100,
    job_name="opt",
    job_num_nodes=20,
    job_partition="node",
    mem_util=10,
    mem_used_percent=10,
    gpu_util=10,
    temperature=10,
    power_draw=10,
    power_used_percent=10,
    retired_pages_count_single_bit=10,
    retired_pages_count_double_bit=10,
)


@report_url(("Scuba", "https://fburl.com/scuba/gcm_githubci/5yfie6uz"))
def test_nvml_publish_scribe(config: Config) -> None:
    api = GraphAPI(
        app_secret=config.graph_api_access_token,
        scribe_category="perfpipe_gcm_githubci",
    )

    api.write(
        data=Log(ts=TEST_TIME, message=[SCRIBE_METRIC]),
        additional_params=SinkAdditionalParams(data_type=DataType.LOG),
    )


@report_url(("ODS", "https://fburl.com/canvas/u1unsdrs"))
def test_nvml_publish_ods(config: Config) -> None:
    api = GraphAPI(
        app_secret=config.graph_api_access_token,
        ods_entity="test.node001",
        scribe_category="perfpipe_gcm_githubci",
    )

    api.write(
        Log(ts=TEST_TIME, message=ODS_METRICS),
        additional_params=SinkAdditionalParams(data_type=DataType.METRIC),
    )
