# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass, field
from typing import (
    Collection,
    Generator,
    Literal,
    Mapping,
    Optional,
    Protocol,
    runtime_checkable,
)

import click
from gcm.exporters import registry

from gcm.monitoring.click import (
    chunk_size_option,
    click_default_cmd,
    cluster_option,
    dry_run_option,
    interval_option,
    log_folder_option,
    log_level_option,
    once_option,
    retries_option,
    sink_option,
    sink_opts_option,
    stdout_option,
)
from gcm.monitoring.clock import Clock, ClockImpl, unixtime_to_pacific_datetime
from gcm.monitoring.kubernetes.client import KubernetesClient
from gcm.monitoring.kubernetes.fake_client import KubernetesFakeClient
from gcm.monitoring.sink.protocol import (
    DataIdentifier,
    DataType,
    SinkAdditionalParams,
    SinkImpl,
)
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.kubernetes.node import KubernetesNodePayload
from gcm.schemas.kubernetes.pod import KubernetesPodPayload

from typeguard import typechecked

try:
    from _typeshed import DataclassInstance
except ImportError:
    from typing import Any as DataclassInstance  # type: ignore[assignment, misc]

LOGGER_NAME = "kubernetes_monitor"
logger = logging.getLogger(LOGGER_NAME)


@runtime_checkable
class CliObject(HasRegistry[SinkImpl], Protocol):
    @property
    def clock(self) -> Clock: ...

    def cluster(self) -> str: ...

    @property
    def kubernetes_client(self) -> KubernetesClient: ...


@dataclass
class CliObjectImpl:
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=lambda: registry)
    clock: Clock = field(default_factory=ClockImpl)
    kubernetes_client: KubernetesClient = field(default_factory=KubernetesFakeClient)
    _cluster: Optional[str] = None

    def cluster(self) -> str:
        if self._cluster is not None:
            return self._cluster
        import clusterscope

        return clusterscope.cluster()


def _make_default_obj() -> CliObject:
    """Construct the default CliObject.

    Uses KubernetesFakeClient as the default since KubernetesApiClient
    requires the optional kubernetes package and in-cluster config.
    The real client is injected via --in-cluster/--no-in-cluster at runtime.
    """
    return CliObjectImpl()


# construct at module-scope because printing sink documentation relies on the object
_default_obj: CliObject = _make_default_obj()


def collect_pod_metrics(
    clock: Clock,
    cluster: str,
    kubernetes_client: KubernetesClient,
    namespace: str,
    label_selector: str,
) -> Generator[DataclassInstance, None, None]:
    log_time = clock.unixtime()
    collection_date = unixtime_to_pacific_datetime(log_time).strftime("%Y-%m-%d")

    for pod_row in kubernetes_client.list_pods(
        namespace=namespace,
        label_selector=label_selector,
    ):
        yield KubernetesPodPayload(
            ds=collection_date,
            collection_unixtime=log_time,
            cluster=cluster,
            pod=pod_row,
        )


def collect_node_conditions(
    clock: Clock,
    cluster: str,
    kubernetes_client: KubernetesClient,
) -> Generator[DataclassInstance, None, None]:
    log_time = clock.unixtime()
    collection_date = unixtime_to_pacific_datetime(log_time).strftime("%Y-%m-%d")

    for condition_row in kubernetes_client.list_node_conditions():
        yield KubernetesNodePayload(
            ds=collection_date,
            collection_unixtime=log_time,
            cluster=cluster,
            node_condition=condition_row,
        )


@click_default_cmd(context_settings={"obj": _default_obj})
@cluster_option
@sink_option
@sink_opts_option
@log_level_option
@log_folder_option
@stdout_option
@interval_option(default=60)
@once_option
@retries_option
@dry_run_option
@chunk_size_option
@click.option(
    "--namespace",
    default="",
    help="Kubernetes namespace to filter pods. Empty string means all namespaces.",
)
@click.option(
    "--in-cluster/--no-in-cluster",
    default=True,
    help="Use in-cluster config (ServiceAccount) or kubeconfig.",
)
@click.option(
    "--label-selector",
    default="",
    help="Kubernetes label selector to filter pods (e.g. 'app=slurm').",
)
@click.pass_obj
@typechecked
def main(
    obj: CliObject,
    cluster: Optional[str],
    sink: str,
    sink_opts: Collection[str],
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    log_folder: str,
    stdout: bool,
    interval: int,
    once: bool,
    retries: int,
    dry_run: bool,
    chunk_size: int,
    namespace: str,
    in_cluster: bool,
    label_selector: str,
) -> None:
    """
    Collects Kubernetes pod and node metrics for SUNK cluster monitoring.
    """
    # Replace the default fake client with the real API client at runtime
    if in_cluster or not isinstance(obj.kubernetes_client, KubernetesFakeClient):
        from gcm.monitoring.kubernetes.api_client import KubernetesApiClient

        if isinstance(obj, CliObjectImpl):
            obj.kubernetes_client = KubernetesApiClient(in_cluster=in_cluster)

    def collect_pods_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[DataclassInstance, None, None]:
        return collect_pod_metrics(
            clock=obj.clock,
            cluster=cluster,
            kubernetes_client=obj.kubernetes_client,
            namespace=namespace,
            label_selector=label_selector,
        )

    def collect_nodes_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[DataclassInstance, None, None]:
        return collect_node_conditions(
            clock=obj.clock,
            cluster=cluster,
            kubernetes_client=obj.kubernetes_client,
        )

    run_data_collection_loop(
        logger_name=LOGGER_NAME,
        log_folder=log_folder,
        stdout=stdout,
        log_level=log_level,
        cluster=obj.cluster() if cluster is None else cluster,
        clock=obj.clock,
        once=once,
        interval=interval,
        data_collection_tasks=[
            (
                collect_pods_callable,
                SinkAdditionalParams(
                    data_type=DataType.METRIC,
                    data_identifier=DataIdentifier.K8S_POD,
                ),
            ),
            (
                collect_nodes_callable,
                SinkAdditionalParams(
                    data_type=DataType.METRIC,
                    data_identifier=DataIdentifier.K8S_NODE,
                ),
            ),
        ],
        sink=sink,
        sink_opts=sink_opts,
        retries=retries,
        chunk_size=chunk_size,
        dry_run=dry_run,
        registry=obj.registry,
    )
