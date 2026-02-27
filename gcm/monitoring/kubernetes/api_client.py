# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import logging
from typing import Iterable

from gcm.monitoring.kubernetes.client import KubernetesClient
from gcm.schemas.kubernetes.node import KubernetesNodeConditionRow
from gcm.schemas.kubernetes.pod import KubernetesPodRow

logger = logging.getLogger(__name__)

_SLURM_JOB_ANNOTATION = "slurm.coreweave.com/job-id"


class KubernetesApiClient(KubernetesClient):
    """Kubernetes client that queries the Kubernetes API via the official Python client.

    Requires the ``kubernetes`` package: ``pip install kubernetes``.
    """

    def __init__(self, *, in_cluster: bool = True) -> None:
        try:
            import kubernetes  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "The 'kubernetes' package is required for KubernetesApiClient. "
                "Install it with: pip install 'gpucm[kubernetes]'"
            )

        from kubernetes import client, config  # type: ignore[import-not-found]

        if in_cluster:
            config.load_incluster_config()
        else:
            config.load_kube_config()

        self._core_api = client.CoreV1Api()

    def list_pods(
        self, namespace: str = "", label_selector: str = ""
    ) -> Iterable[KubernetesPodRow]:
        try:
            if namespace:
                response = self._core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=label_selector,
                )
            else:
                response = self._core_api.list_pod_for_all_namespaces(
                    label_selector=label_selector,
                )
        except Exception as e:
            raise RuntimeError(f"Failed to list pods: {e}") from e

        for pod in response.items:
            annotations = pod.metadata.annotations or {}
            slurm_job_id = annotations.get(_SLURM_JOB_ANNOTATION)

            container_statuses = pod.status.container_statuses or []
            if container_statuses:
                for cs in container_statuses:
                    yield KubernetesPodRow(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                        node_name=pod.spec.node_name,
                        phase=pod.status.phase,
                        restart_count=cs.restart_count,
                        container_name=cs.name,
                        slurm_job_id=slurm_job_id,
                    )
            else:
                yield KubernetesPodRow(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    node_name=pod.spec.node_name,
                    phase=pod.status.phase,
                    restart_count=0,
                    container_name=None,
                    slurm_job_id=slurm_job_id,
                )

    def list_node_conditions(self) -> Iterable[KubernetesNodeConditionRow]:
        try:
            response = self._core_api.list_node()
        except Exception as e:
            raise RuntimeError(f"Failed to list nodes: {e}") from e

        for node in response.items:
            conditions = node.status.conditions or []
            for condition in conditions:
                yield KubernetesNodeConditionRow(
                    name=node.metadata.name,
                    condition_type=condition.type,
                    status=condition.status,
                    reason=condition.reason,
                    message=condition.message,
                )
