# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from pydantic import AliasPath, BaseModel, Field

_API_URL = "https://kubernetes.default.svc"
_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
_CA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
_ACTIVE_POD_PHASES = {"Pending", "Running", "Unknown"}


@dataclass(frozen=True)
class KubernetesMetadata:
    pods: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KubernetesMetadataConfig:
    keys: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Optional["KubernetesMetadataConfig"]:
        if os.getenv("GCM_KUBERNETES_METADATA_ENABLED", "false") != "true":
            return None
        return cls(keys=_split_env("GCM_KUBERNETES_METADATA_KEYS"))


class _PodMetadata(BaseModel):
    name: str
    namespace: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)


class _Pod(BaseModel):
    metadata: _PodMetadata
    status: Optional[str] = Field(
        default=None, validation_alias=AliasPath("status", "phase")
    )


def _split_env(name: str) -> tuple[str, ...]:
    return tuple(
        part.strip() for part in os.getenv(name, "").split(",") if part.strip()
    )


def _serialize_pod_metadata(pods: list[_Pod], selected_keys: set[str]) -> list[str]:
    serialized_pods: list[str] = []
    for pod in sorted(
        pods, key=lambda item: (item.metadata.namespace, item.metadata.name)
    ):
        if pod.status not in _ACTIVE_POD_PHASES:
            continue

        labels = {
            key: value
            for key, value in pod.metadata.labels.items()
            if key in selected_keys
        }
        annotations = {
            key: value
            for key, value in pod.metadata.annotations.items()
            if key in selected_keys
        }

        if not labels and not annotations:
            continue

        serialized_pods.append(
            json.dumps(
                {
                    "namespace": pod.metadata.namespace,
                    "name": pod.metadata.name,
                    "labels": labels,
                    "annotations": annotations,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    return serialized_pods


def get_kubernetes_metadata(node: str) -> Optional[KubernetesMetadata]:
    config = KubernetesMetadataConfig.from_env()
    if config is None:
        return None

    selected_keys = set(config.keys)
    if not selected_keys:
        return None

    node_name = os.getenv("NODE_NAME", node)
    response = requests.get(
        f"{_API_URL}/api/v1/pods",
        headers={"Authorization": f"Bearer {_TOKEN_PATH.read_text().strip()}"},
        params={"fieldSelector": f"spec.nodeName={node_name}"},
        timeout=3,
        verify=str(_CA_PATH),
    )
    response.raise_for_status()
    pods = [_Pod.model_validate(item) for item in response.json()["items"]]
    serialized_pods = _serialize_pod_metadata(pods, selected_keys)

    return KubernetesMetadata(pods=serialized_pods)
