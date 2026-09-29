# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from typing import Iterable, Protocol

from gcm.schemas.kubernetes.node import KubernetesNodeConditionRow
from gcm.schemas.kubernetes.pod import KubernetesPodRow


class KubernetesClient(Protocol):
    """A low-level Kubernetes client for pod and node monitoring."""

    def list_pods(
        self, namespace: str = "", label_selector: str = ""
    ) -> Iterable[KubernetesPodRow]:
        """Get pod information from the Kubernetes API.

        Args:
            namespace: Kubernetes namespace to filter pods. Empty string means all namespaces.
            label_selector: Kubernetes label selector to filter pods.

        If an error occurs during execution, RuntimeError should be raised.
        """

    def list_node_conditions(self) -> Iterable[KubernetesNodeConditionRow]:
        """Get node condition information from the Kubernetes API.

        If an error occurs during execution, RuntimeError should be raised.
        """


def get_pod_node_mapping(
    client: KubernetesClient,
    namespace: str = "",
    label_selector: str = "",
) -> dict[str, str]:
    return {
        pod.name: pod.node_name
        for pod in client.list_pods(
            namespace=namespace,
            label_selector=label_selector,
        )
        if pod.name is not None and pod.node_name is not None
    }
