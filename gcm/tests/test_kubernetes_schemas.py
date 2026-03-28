# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import unittest

from gcm.monitoring.kubernetes.client import KubernetesClient
from gcm.schemas.kubernetes.node import (
    KubernetesNodeConditionRow,
    KubernetesNodePayload,
)
from gcm.schemas.kubernetes.pod import KubernetesPodPayload, KubernetesPodRow


class TestKubernetesPodRow(unittest.TestCase):
    def test_default_values(self) -> None:
        row = KubernetesPodRow()
        self.assertIsNone(row.name)
        self.assertIsNone(row.namespace)
        self.assertIsNone(row.node_name)
        self.assertIsNone(row.phase)
        self.assertIsNone(row.restart_count)
        self.assertIsNone(row.container_name)
        self.assertIsNone(row.slurm_job_id)

    def test_with_values(self) -> None:
        row = KubernetesPodRow(
            name="my-pod",
            namespace="default",
            node_name="node-1",
            phase="Running",
            restart_count=3,
            container_name="main",
            slurm_job_id="12345",
        )
        self.assertEqual(row.name, "my-pod")
        self.assertEqual(row.namespace, "default")
        self.assertEqual(row.node_name, "node-1")
        self.assertEqual(row.phase, "Running")
        self.assertEqual(row.restart_count, 3)
        self.assertEqual(row.container_name, "main")
        self.assertEqual(row.slurm_job_id, "12345")


class TestKubernetesPodPayload(unittest.TestCase):
    def test_payload_with_pod(self) -> None:
        row = KubernetesPodRow(name="my-pod", phase="Running")
        payload = KubernetesPodPayload(
            ds="2026-02-27",
            collection_unixtime=1740700000,
            cluster="test-cluster",
            pod=row,
        )
        self.assertEqual(payload.ds, "2026-02-27")
        self.assertEqual(payload.collection_unixtime, 1740700000)
        self.assertEqual(payload.cluster, "test-cluster")
        self.assertEqual(payload.pod.name, "my-pod")
        self.assertIsNone(payload.derived_cluster)

    def test_payload_with_derived_cluster(self) -> None:
        row = KubernetesPodRow(name="my-pod")
        payload = KubernetesPodPayload(
            ds="2026-02-27",
            collection_unixtime=1740700000,
            cluster="test-cluster",
            derived_cluster="derived-1",
            pod=row,
        )
        self.assertEqual(payload.derived_cluster, "derived-1")


class TestKubernetesNodeConditionRow(unittest.TestCase):
    def test_default_values(self) -> None:
        row = KubernetesNodeConditionRow()
        self.assertIsNone(row.name)
        self.assertIsNone(row.condition_type)
        self.assertIsNone(row.status)
        self.assertIsNone(row.reason)
        self.assertIsNone(row.message)

    def test_with_values(self) -> None:
        row = KubernetesNodeConditionRow(
            name="node-1",
            condition_type="Ready",
            status="True",
            reason="KubeletReady",
            message="kubelet is posting ready status",
        )
        self.assertEqual(row.name, "node-1")
        self.assertEqual(row.condition_type, "Ready")
        self.assertEqual(row.status, "True")
        self.assertEqual(row.reason, "KubeletReady")


class TestKubernetesNodePayload(unittest.TestCase):
    def test_payload_with_node_condition(self) -> None:
        row = KubernetesNodeConditionRow(
            name="node-1", condition_type="Ready", status="True"
        )
        payload = KubernetesNodePayload(
            ds="2026-02-27",
            collection_unixtime=1740700000,
            cluster="test-cluster",
            node_condition=row,
        )
        self.assertEqual(payload.ds, "2026-02-27")
        self.assertEqual(payload.cluster, "test-cluster")
        self.assertEqual(payload.node_condition.name, "node-1")
        self.assertIsNone(payload.derived_cluster)


class TestKubernetesClientProtocol(unittest.TestCase):
    def test_protocol_is_importable(self) -> None:
        """Verify the protocol can be imported and used as a type."""
        self.assertTrue(hasattr(KubernetesClient, "list_pods"))
        self.assertTrue(hasattr(KubernetesClient, "list_node_conditions"))


if __name__ == "__main__":
    unittest.main()
