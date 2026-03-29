# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from gcm.monitoring.kubernetes.client import KubernetesClient
from gcm.schemas.kubernetes.node import KubernetesNodeConditionRow
from gcm.schemas.kubernetes.pod import KubernetesPodRow


@dataclass
class KubernetesFakeClient(KubernetesClient):
    """A fake Kubernetes client for testing with injectable pod and node data."""

    pods: List[KubernetesPodRow] = field(default_factory=list)
    node_conditions: List[KubernetesNodeConditionRow] = field(default_factory=list)

    def list_pods(
        self, namespace: str = "", label_selector: str = ""
    ) -> Iterable[KubernetesPodRow]:
        for pod in self.pods:
            if namespace and pod.namespace != namespace:
                continue
            yield pod

    def list_node_conditions(self) -> Iterable[KubernetesNodeConditionRow]:
        yield from self.node_conditions
