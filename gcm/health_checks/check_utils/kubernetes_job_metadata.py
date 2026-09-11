import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from pydantic import BaseModel, Field

_API_URL = "https://kubernetes.default.svc"
_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
_CA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
_ACTIVE_POD_PHASES = {"Pending", "Running", "Unknown"}


@dataclass(frozen=True)
class KubernetesJobMetadata:
    active_job_ids: list[str] = field(default_factory=list)
    active_users: list[str] = field(default_factory=list)
    active_org_ids: list[str] = field(default_factory=list)
    active_project_ids: list[str] = field(default_factory=list)
    active_pod_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KubernetesJobMetadataConfig:
    namespace: str
    label_selector: str
    job_id_label: str
    user_label: str
    org_id_label: str
    project_id_label: str

    @classmethod
    def from_env(cls) -> Optional["KubernetesJobMetadataConfig"]:
        if os.getenv("GCM_KUBERNETES_JOB_METADATA_ENABLED") != "true":
            return None
        namespace = os.getenv("GCM_KUBERNETES_JOB_NAMESPACE", "")
        job_id_label = os.getenv("GCM_KUBERNETES_JOB_ID_LABEL", "")
        if not namespace or not job_id_label:
            raise ValueError(
                "Kubernetes job metadata requires a namespace and job ID label"
            )
        return cls(
            namespace=namespace,
            label_selector=os.getenv("GCM_KUBERNETES_JOB_LABEL_SELECTOR", ""),
            job_id_label=job_id_label,
            user_label=os.getenv("GCM_KUBERNETES_USER_LABEL", ""),
            org_id_label=os.getenv("GCM_KUBERNETES_ORG_ID_LABEL", ""),
            project_id_label=os.getenv("GCM_KUBERNETES_PROJECT_ID_LABEL", ""),
        )


class _PodMetadata(BaseModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class _PodStatus(BaseModel):
    phase: Optional[str] = None


class _Pod(BaseModel):
    metadata: _PodMetadata
    status: _PodStatus


class _PodList(BaseModel):
    items: list[_Pod]


def get_kubernetes_job_metadata(node: str) -> Optional[KubernetesJobMetadata]:
    config = KubernetesJobMetadataConfig.from_env()
    if config is None:
        return None

    query_node = os.getenv("NODE_NAME", node)
    response = requests.get(
        f"{_API_URL}/api/v1/namespaces/{quote(config.namespace, safe='')}/pods",
        headers={"Authorization": f"Bearer {_TOKEN_PATH.read_text().strip()}"},
        params={
            "fieldSelector": f"spec.nodeName={query_node}",
            "labelSelector": config.label_selector,
        },
        timeout=3,
        verify=str(_CA_PATH),
    )
    response.raise_for_status()
    pods = _PodList.model_validate(response.json()).items

    by_job: dict[str, tuple[str, str, str, str]] = {}
    for pod in pods:
        if pod.status.phase not in _ACTIVE_POD_PHASES:
            continue
        labels = pod.metadata.labels
        job_id = labels.get(config.job_id_label, "")
        if not job_id:
            continue
        candidate = (
            labels.get(config.user_label, ""),
            labels.get(config.org_id_label, ""),
            labels.get(config.project_id_label, ""),
            pod.metadata.name,
        )
        current = by_job.get(job_id)
        if current is None or candidate[3] < current[3]:
            by_job[job_id] = candidate

    job_ids: list[str] = []
    users: list[str] = []
    org_ids: list[str] = []
    project_ids: list[str] = []
    pod_names: list[str] = []
    for job_id, (user, org_id, project_id, pod_name) in sorted(by_job.items()):
        job_ids.append(job_id)
        users.append(user)
        org_ids.append(org_id)
        project_ids.append(project_id)
        pod_names.append(pod_name)
    return KubernetesJobMetadata(
        active_job_ids=job_ids,
        active_users=users,
        active_org_ids=org_ids,
        active_project_ids=project_ids,
        active_pod_names=pod_names,
    )
