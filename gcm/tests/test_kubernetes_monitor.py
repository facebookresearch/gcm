# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import unittest
from dataclasses import dataclass, field
from typing import Mapping

from gcm.monitoring.cli.kubernetes_monitor import (
    collect_node_conditions,
    collect_pod_metrics,
)
from gcm.monitoring.clock import Clock
from gcm.monitoring.kubernetes.client import KubernetesClient
from gcm.monitoring.kubernetes.fake_client import KubernetesFakeClient
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.schemas.kubernetes.node import (
    KubernetesNodeConditionRow,
    KubernetesNodePayload,
)
from gcm.schemas.kubernetes.pod import KubernetesPodPayload, KubernetesPodRow


class FakeClock(Clock):
    def unixtime(self) -> int:
        return 1740700000


class FakeSink:
    def __init__(self) -> None:
        self.data: list[object] = []

    def write(self, data: object, additional_params: object) -> None:
        self.data.append(data)


@dataclass
class FakeCliObject:
    clock: Clock = field(default_factory=FakeClock)
    kubernetes_client: KubernetesClient = field(default_factory=KubernetesFakeClient)
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=dict)
    _cluster: str = "test-cluster"

    def cluster(self) -> str:
        return self._cluster


class TestCollectPodMetrics(unittest.TestCase):
    def test_yields_pod_payloads(self) -> None:
        pods = [
            KubernetesPodRow(name="pod-1", namespace="ns-1", phase="Running"),
            KubernetesPodRow(name="pod-2", namespace="ns-2", phase="Pending"),
        ]
        client = KubernetesFakeClient(pods=pods)
        clock = FakeClock()

        results = list(
            collect_pod_metrics(
                clock=clock,
                cluster="test-cluster",
                kubernetes_client=client,
                namespace="",
                label_selector="",
            )
        )

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], KubernetesPodPayload)
        self.assertEqual(results[0].pod.name, "pod-1")
        self.assertEqual(results[0].cluster, "test-cluster")
        self.assertEqual(results[1].pod.name, "pod-2")

    def test_filters_by_namespace(self) -> None:
        pods = [
            KubernetesPodRow(name="pod-1", namespace="ns-1", phase="Running"),
            KubernetesPodRow(name="pod-2", namespace="ns-2", phase="Pending"),
        ]
        client = KubernetesFakeClient(pods=pods)
        clock = FakeClock()

        results = list(
            collect_pod_metrics(
                clock=clock,
                cluster="test-cluster",
                kubernetes_client=client,
                namespace="ns-1",
                label_selector="",
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pod.name, "pod-1")

    def test_empty_pods(self) -> None:
        client = KubernetesFakeClient()
        clock = FakeClock()

        results = list(
            collect_pod_metrics(
                clock=clock,
                cluster="test-cluster",
                kubernetes_client=client,
                namespace="",
                label_selector="",
            )
        )

        self.assertEqual(len(results), 0)

    def test_payload_fields(self) -> None:
        pods = [
            KubernetesPodRow(
                name="pod-1",
                namespace="default",
                phase="Running",
                restart_count=3,
                slurm_job_id="12345",
            ),
        ]
        client = KubernetesFakeClient(pods=pods)
        clock = FakeClock()

        results = list(
            collect_pod_metrics(
                clock=clock,
                cluster="my-cluster",
                kubernetes_client=client,
                namespace="",
                label_selector="",
            )
        )

        payload = results[0]
        self.assertEqual(payload.collection_unixtime, 1740700000)
        self.assertEqual(payload.cluster, "my-cluster")
        self.assertEqual(payload.pod.restart_count, 3)
        self.assertEqual(payload.pod.slurm_job_id, "12345")


class TestCollectNodeConditions(unittest.TestCase):
    def test_yields_node_payloads(self) -> None:
        conditions = [
            KubernetesNodeConditionRow(
                name="node-1", condition_type="Ready", status="True"
            ),
            KubernetesNodeConditionRow(
                name="node-1", condition_type="MemoryPressure", status="False"
            ),
        ]
        client = KubernetesFakeClient(node_conditions=conditions)
        clock = FakeClock()

        results = list(
            collect_node_conditions(
                clock=clock,
                cluster="test-cluster",
                kubernetes_client=client,
            )
        )

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], KubernetesNodePayload)
        self.assertEqual(results[0].node_condition.condition_type, "Ready")
        self.assertEqual(results[1].node_condition.condition_type, "MemoryPressure")

    def test_empty_conditions(self) -> None:
        client = KubernetesFakeClient()
        clock = FakeClock()

        results = list(
            collect_node_conditions(
                clock=clock,
                cluster="test-cluster",
                kubernetes_client=client,
            )
        )

        self.assertEqual(len(results), 0)


class TestCliObjectProtocol(unittest.TestCase):
    def test_fake_cli_object_satisfies_protocol(self) -> None:
        """FakeCliObject should satisfy the CliObject protocol."""
        fake = FakeCliObject()
        # Verify it has the expected interface
        self.assertTrue(hasattr(fake, "clock"))
        self.assertTrue(hasattr(fake, "kubernetes_client"))
        self.assertTrue(callable(fake.cluster))
        self.assertEqual(fake.cluster(), "test-cluster")


if __name__ == "__main__":
    unittest.main()
