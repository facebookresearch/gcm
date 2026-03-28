# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import unittest
from unittest.mock import MagicMock, patch

from gcm.monitoring.kubernetes.fake_client import KubernetesFakeClient
from gcm.schemas.kubernetes.node import KubernetesNodeConditionRow
from gcm.schemas.kubernetes.pod import KubernetesPodRow


class TestKubernetesFakeClient(unittest.TestCase):
    def test_list_pods_empty(self) -> None:
        client = KubernetesFakeClient()
        self.assertEqual(list(client.list_pods()), [])

    def test_list_pods_returns_all(self) -> None:
        pods = [
            KubernetesPodRow(name="pod-1", namespace="ns-1", phase="Running"),
            KubernetesPodRow(name="pod-2", namespace="ns-2", phase="Pending"),
        ]
        client = KubernetesFakeClient(pods=pods)
        result = list(client.list_pods())
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "pod-1")
        self.assertEqual(result[1].name, "pod-2")

    def test_list_pods_filters_by_namespace(self) -> None:
        pods = [
            KubernetesPodRow(name="pod-1", namespace="ns-1", phase="Running"),
            KubernetesPodRow(name="pod-2", namespace="ns-2", phase="Pending"),
        ]
        client = KubernetesFakeClient(pods=pods)
        result = list(client.list_pods(namespace="ns-1"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "pod-1")

    def test_list_node_conditions_empty(self) -> None:
        client = KubernetesFakeClient()
        self.assertEqual(list(client.list_node_conditions()), [])

    def test_list_node_conditions_returns_all(self) -> None:
        conditions = [
            KubernetesNodeConditionRow(
                name="node-1", condition_type="Ready", status="True"
            ),
            KubernetesNodeConditionRow(
                name="node-1", condition_type="MemoryPressure", status="False"
            ),
        ]
        client = KubernetesFakeClient(node_conditions=conditions)
        result = list(client.list_node_conditions())
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].condition_type, "Ready")
        self.assertEqual(result[1].condition_type, "MemoryPressure")

    def test_list_pods_with_slurm_job_id(self) -> None:
        pods = [
            KubernetesPodRow(
                name="slurm-pod",
                namespace="default",
                phase="Running",
                slurm_job_id="12345",
            ),
        ]
        client = KubernetesFakeClient(pods=pods)
        result = list(client.list_pods())
        self.assertEqual(result[0].slurm_job_id, "12345")


class TestKubernetesApiClient(unittest.TestCase):
    def test_import_error_raises_runtime_error(self) -> None:
        """Verify that missing kubernetes package raises RuntimeError."""
        with patch.dict("sys.modules", {"kubernetes": None}):
            # Reload to pick up the patched import
            import importlib

            from gcm.monitoring.kubernetes import api_client

            importlib.reload(api_client)
            with self.assertRaises(RuntimeError) as ctx:
                api_client.KubernetesApiClient(in_cluster=False)
            self.assertIn("kubernetes", str(ctx.exception))

    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient.__init__")
    def test_list_pods_with_containers(self, mock_init: MagicMock) -> None:
        """Test list_pods extracts pod data correctly from K8s API response."""
        mock_init.return_value = None

        from gcm.monitoring.kubernetes.api_client import (
            _SLURM_JOB_ANNOTATION,
            KubernetesApiClient,
        )

        client = KubernetesApiClient.__new__(KubernetesApiClient)
        client._core_api = MagicMock()

        # Build mock pod with container status
        mock_container_status = MagicMock()
        mock_container_status.name = "main"
        mock_container_status.restart_count = 5

        mock_pod = MagicMock()
        mock_pod.metadata.name = "test-pod"
        mock_pod.metadata.namespace = "default"
        mock_pod.metadata.annotations = {_SLURM_JOB_ANNOTATION: "99999"}
        mock_pod.spec.node_name = "node-1"
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = [mock_container_status]

        mock_response = MagicMock()
        mock_response.items = [mock_pod]
        client._core_api.list_pod_for_all_namespaces.return_value = mock_response

        result = list(client.list_pods())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "test-pod")
        self.assertEqual(result[0].namespace, "default")
        self.assertEqual(result[0].node_name, "node-1")
        self.assertEqual(result[0].phase, "Running")
        self.assertEqual(result[0].restart_count, 5)
        self.assertEqual(result[0].container_name, "main")
        self.assertEqual(result[0].slurm_job_id, "99999")

    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient.__init__")
    def test_list_pods_without_containers(self, mock_init: MagicMock) -> None:
        """Test list_pods handles pods with no container statuses."""
        mock_init.return_value = None

        from gcm.monitoring.kubernetes.api_client import KubernetesApiClient

        client = KubernetesApiClient.__new__(KubernetesApiClient)
        client._core_api = MagicMock()

        mock_pod = MagicMock()
        mock_pod.metadata.name = "pending-pod"
        mock_pod.metadata.namespace = "kube-system"
        mock_pod.metadata.annotations = {}
        mock_pod.spec.node_name = None
        mock_pod.status.phase = "Pending"
        mock_pod.status.container_statuses = None

        mock_response = MagicMock()
        mock_response.items = [mock_pod]
        client._core_api.list_pod_for_all_namespaces.return_value = mock_response

        result = list(client.list_pods())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "pending-pod")
        self.assertEqual(result[0].restart_count, 0)
        self.assertIsNone(result[0].container_name)
        self.assertIsNone(result[0].slurm_job_id)

    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient.__init__")
    def test_list_pods_with_namespace_filter(self, mock_init: MagicMock) -> None:
        """Test list_pods calls list_namespaced_pod when namespace is specified."""
        mock_init.return_value = None

        from gcm.monitoring.kubernetes.api_client import KubernetesApiClient

        client = KubernetesApiClient.__new__(KubernetesApiClient)
        client._core_api = MagicMock()

        mock_response = MagicMock()
        mock_response.items = []
        client._core_api.list_namespaced_pod.return_value = mock_response

        list(client.list_pods(namespace="my-ns", label_selector="app=test"))
        client._core_api.list_namespaced_pod.assert_called_once_with(
            namespace="my-ns",
            label_selector="app=test",
        )

    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient.__init__")
    def test_list_node_conditions(self, mock_init: MagicMock) -> None:
        """Test list_node_conditions extracts conditions correctly."""
        mock_init.return_value = None

        from gcm.monitoring.kubernetes.api_client import KubernetesApiClient

        client = KubernetesApiClient.__new__(KubernetesApiClient)
        client._core_api = MagicMock()

        mock_condition = MagicMock()
        mock_condition.type = "Ready"
        mock_condition.status = "True"
        mock_condition.reason = "KubeletReady"
        mock_condition.message = "kubelet is posting ready status"

        mock_node = MagicMock()
        mock_node.metadata.name = "node-1"
        mock_node.status.conditions = [mock_condition]

        mock_response = MagicMock()
        mock_response.items = [mock_node]
        client._core_api.list_node.return_value = mock_response

        result = list(client.list_node_conditions())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "node-1")
        self.assertEqual(result[0].condition_type, "Ready")
        self.assertEqual(result[0].status, "True")
        self.assertEqual(result[0].reason, "KubeletReady")

    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient.__init__")
    def test_list_pods_api_error_raises_runtime_error(
        self, mock_init: MagicMock
    ) -> None:
        """Test that API errors are wrapped in RuntimeError."""
        mock_init.return_value = None

        from gcm.monitoring.kubernetes.api_client import KubernetesApiClient

        client = KubernetesApiClient.__new__(KubernetesApiClient)
        client._core_api = MagicMock()
        client._core_api.list_pod_for_all_namespaces.side_effect = Exception(
            "connection refused"
        )

        with self.assertRaises(RuntimeError) as ctx:
            list(client.list_pods())
        self.assertIn("Failed to list pods", str(ctx.exception))

    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient.__init__")
    def test_list_node_conditions_api_error_raises_runtime_error(
        self, mock_init: MagicMock
    ) -> None:
        """Test that node API errors are wrapped in RuntimeError."""
        mock_init.return_value = None

        from gcm.monitoring.kubernetes.api_client import KubernetesApiClient

        client = KubernetesApiClient.__new__(KubernetesApiClient)
        client._core_api = MagicMock()
        client._core_api.list_node.side_effect = Exception("forbidden")

        with self.assertRaises(RuntimeError) as ctx:
            list(client.list_node_conditions())
        self.assertIn("Failed to list nodes", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
