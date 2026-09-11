# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from pathlib import Path

import pytest
import requests_mock

from gcm.health_checks.check_utils import kubernetes_job_metadata


def configure_job_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    token_path = tmp_path / "token"
    token_path.write_text("service-account-token")
    monkeypatch.setattr(kubernetes_job_metadata, "_TOKEN_PATH", token_path)
    monkeypatch.setattr(kubernetes_job_metadata, "_CA_PATH", tmp_path / "ca.crt")
    monkeypatch.setenv("GCM_KUBERNETES_JOB_METADATA_ENABLED", "true")
    monkeypatch.setenv("GCM_KUBERNETES_JOB_NAMESPACE", "dispatch")
    monkeypatch.setenv(
        "GCM_KUBERNETES_JOB_LABEL_SELECTOR",
        "ac-dispatch/managed=true,ac-dispatch/type=job",
    )
    monkeypatch.setenv("GCM_KUBERNETES_JOB_ID_LABEL", "ac-dispatch/job-id")
    monkeypatch.setenv("GCM_KUBERNETES_USER_LABEL", "ac-dispatch/user")
    monkeypatch.setenv("GCM_KUBERNETES_ORG_ID_LABEL", "ac-dispatch/org-id")
    monkeypatch.setenv("GCM_KUBERNETES_PROJECT_ID_LABEL", "ac-dispatch/project-id")


def test_get_kubernetes_job_metadata_returns_active_jobs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    requests_mock: requests_mock.Mocker,
) -> None:
    configure_job_metadata(monkeypatch, tmp_path)
    requests_mock.get(
        "https://kubernetes.default.svc/api/v1/namespaces/dispatch/pods",
        json={
            "items": [
                {
                    "metadata": {
                        "name": "job-b-worker-0",
                        "labels": {
                            "ac-dispatch/job-id": "job-b",
                            "ac-dispatch/user": "bob",
                            "ac-dispatch/org-id": "org-b",
                            "ac-dispatch/project-id": "project-b",
                        },
                    },
                    "status": {"phase": "Running"},
                },
                {
                    "metadata": {
                        "name": "job-a-worker-1",
                        "labels": {
                            "ac-dispatch/job-id": "job-a",
                            "ac-dispatch/user": "alice",
                        },
                    },
                    "status": {"phase": "Pending"},
                },
                {
                    "metadata": {
                        "name": "job-a-worker-0",
                        "labels": {
                            "ac-dispatch/job-id": "job-a",
                            "ac-dispatch/user": "alice",
                        },
                    },
                    "status": {"phase": "Running"},
                },
                {
                    "metadata": {
                        "name": "job-old-worker-0",
                        "labels": {"ac-dispatch/job-id": "job-old"},
                    },
                    "status": {"phase": "Succeeded"},
                },
            ]
        },
    )

    metadata = kubernetes_job_metadata.get_kubernetes_job_metadata("gpu-1")

    assert metadata is not None
    assert metadata.active_job_ids == ["job-a", "job-b"]
    assert metadata.active_users == ["alice", "bob"]
    assert metadata.active_org_ids == ["", "org-b"]
    assert metadata.active_project_ids == ["", "project-b"]
    assert metadata.active_pod_names == ["job-a-worker-0", "job-b-worker-0"]
    assert requests_mock.last_request is not None
    assert requests_mock.last_request.qs["fieldselector"] == ["spec.nodename=gpu-1"]
    assert requests_mock.last_request.qs["labelselector"] == [
        "ac-dispatch/managed=true,ac-dispatch/type=job"
    ]
    assert requests_mock.last_request.headers["Authorization"] == (
        "Bearer service-account-token"
    )


def test_get_kubernetes_job_metadata_is_disabled_by_default(
    requests_mock: requests_mock.Mocker,
) -> None:
    assert kubernetes_job_metadata.get_kubernetes_job_metadata("gpu-1") is None
    assert not requests_mock.called
