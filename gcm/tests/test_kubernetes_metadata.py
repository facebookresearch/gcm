# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from unittest.mock import patch

from gcm.health_checks.check_utils import kubernetes_metadata


def test_kubernetes_metadata_config_parses_keys() -> None:
    with patch.dict(
        "os.environ",
        {
            "GCM_KUBERNETES_METADATA_ENABLED": "true",
            "GCM_KUBERNETES_METADATA_KEYS": (
                " example.com/job-id, ,example.com/owner "
            ),
        },
        clear=True,
    ):
        assert kubernetes_metadata.KubernetesMetadataConfig.from_env() == (
            kubernetes_metadata.KubernetesMetadataConfig(
                keys=("example.com/job-id", "example.com/owner")
            )
        )


def test_serialize_pod_metadata_selects_active_pods_and_requested_keys() -> None:
    pods = [
        kubernetes_metadata._Pod.model_validate(pod)
        for pod in [
            {
                "metadata": {
                    "name": "job-b-worker-0",
                    "namespace": "team-b",
                    "labels": {
                        "example.com/job-id": "job-b",
                        "example.com/user": "bob",
                        "unrelated": "ignored",
                    },
                    "annotations": {
                        "example.com/name": "training-run",
                        "unrelated": "ignored",
                    },
                },
                "status": {"phase": "Running"},
            },
            {
                "metadata": {
                    "name": "job-a-worker-0",
                    "namespace": "team-a",
                    "labels": {
                        "example.com/job-id": "job-a",
                        "example.com/user": "alice",
                    },
                },
                "status": {"phase": "Pending"},
            },
            {
                "metadata": {
                    "name": "completed-worker-0",
                    "namespace": "team-a",
                    "labels": {"example.com/job-id": "job-old"},
                },
                "status": {"phase": "Succeeded"},
            },
            {
                "metadata": {
                    "name": "system-agent",
                    "namespace": "kube-system",
                    "labels": {"app": "system-agent"},
                },
                "status": {"phase": "Running"},
            },
        ]
    ]

    serialized_pods = kubernetes_metadata._serialize_pod_metadata(
        pods,
        {
            "example.com/job-id",
            "example.com/user",
            "example.com/name",
        },
    )

    assert [json.loads(pod) for pod in serialized_pods] == [
        {
            "namespace": "team-a",
            "name": "job-a-worker-0",
            "labels": {
                "example.com/job-id": "job-a",
                "example.com/user": "alice",
            },
            "annotations": {},
        },
        {
            "namespace": "team-b",
            "name": "job-b-worker-0",
            "labels": {
                "example.com/job-id": "job-b",
                "example.com/user": "bob",
            },
            "annotations": {"example.com/name": "training-run"},
        },
    ]
