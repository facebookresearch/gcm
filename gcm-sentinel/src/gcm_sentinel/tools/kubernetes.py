# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import json
import logging

from kubernetes import client

from gcm_sentinel.k8s import get_core_api

logger = logging.getLogger(__name__)




# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------

async def get_node_info(node_name: str) -> str:
    api = get_core_api()
    node = api.read_node(node_name)

    info = {
        "name": node_name,
        "labels": dict(node.metadata.labels or {}),
        "annotations": {
            k: v for k, v in (node.metadata.annotations or {}).items()
            if k.startswith("gcm-sentinel") or k.startswith("node.kubernetes.io/")
        },
        "taints": [
            {"key": t.key, "value": t.value or "", "effect": t.effect}
            for t in (node.spec.taints or [])
        ],
        "conditions": [
            {
                "type": c.type, "status": c.status,
                "reason": c.reason or "", "message": c.message or "",
                "lastTransitionTime": str(c.last_transition_time),
            }
            for c in (node.status.conditions or [])
        ],
        "allocatable": {k: str(v) for k, v in (node.status.allocatable or {}).items()},
        "capacity": {k: str(v) for k, v in (node.status.capacity or {}).items()},
        "pods": [
            {"name": p.metadata.name, "namespace": p.metadata.namespace, "phase": p.status.phase}
            for p in api.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name}"
            ).items[:50]
        ],
    }
    return json.dumps(info, indent=2, default=str)


async def get_node_events(node_name: str) -> str:
    api = get_core_api()
    events = api.list_event_for_all_namespaces(
        field_selector=f"involvedObject.name={node_name},involvedObject.kind=Node",
    )
    result = [
        {
            "type": e.type, "reason": e.reason or "",
            "message": (e.message or "")[:300],
            "source": e.source.component if e.source else "",
            "count": e.count,
            "firstTimestamp": str(e.first_timestamp),
            "lastTimestamp": str(e.last_timestamp),
        }
        for e in events.items[-50:]
    ]
    return json.dumps(result, indent=2, default=str)


async def get_pod_logs(node_name: str, pod_name_pattern: str = "", tail_lines: int = 100) -> str:
    api = get_core_api()
    pods = api.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
    monitoring_patterns = ["dcgm", "npd", "node-problem", "gcm", "gpu"]

    results = {}
    for pod in pods.items:
        name, ns = pod.metadata.name, pod.metadata.namespace
        if pod_name_pattern:
            if pod_name_pattern.lower() not in name.lower():
                continue
        elif not any(p in name.lower() for p in monitoring_patterns):
            continue

        try:
            container = pod.spec.containers[0].name if pod.spec.containers else None
            if not container:
                continue
            logs = api.read_namespaced_pod_log(
                name=name, namespace=ns, container=container,
                tail_lines=tail_lines, timestamps=True,
            )
            results[f"{ns}/{name}"] = logs[-3000:]
        except Exception as exc:
            results[f"{ns}/{name}"] = f"error: {exc}"

        if len(results) >= 5:
            break

    return json.dumps(results, indent=2) if results else "No matching pods found."


async def get_workload_info(node_name: str) -> str:
    api = get_core_api()
    pods = api.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
    system_ns = {"kube-system", "monitoring", "kube-node-lease", "kube-public"}

    workloads = []
    for pod in pods.items:
        ns = pod.metadata.namespace
        if ns in system_ns:
            continue
        owner_refs = pod.metadata.owner_references or []
        if any(ref.kind == "DaemonSet" for ref in owner_refs):
            continue

        gpu_req = "0"
        for c in pod.spec.containers or []:
            reqs = (c.resources.requests or {}) if c.resources else {}
            if "nvidia.com/gpu" in reqs:
                gpu_req = str(reqs["nvidia.com/gpu"])
        if gpu_req == "0":
            continue

        container_statuses = []
        for cs in pod.status.container_statuses or []:
            s = {"name": cs.name, "ready": cs.ready, "restartCount": cs.restart_count}
            if cs.state:
                if cs.state.running:
                    s["state"] = "running"
                elif cs.state.waiting:
                    s["state"] = f"waiting: {cs.state.waiting.reason}"
                elif cs.state.terminated:
                    s["state"] = f"terminated: {cs.state.terminated.reason} (exit {cs.state.terminated.exit_code})"
            container_statuses.append(s)

        # Find sibling pods from the same Job owner.
        siblings = []
        for ref in owner_refs:
            if ref.kind == "Job":
                try:
                    for sp in api.list_namespaced_pod(ns, label_selector=f"job-name={ref.name}").items:
                        if sp.metadata.name != pod.metadata.name:
                            siblings.append({"name": sp.metadata.name, "node": sp.spec.node_name, "phase": sp.status.phase})
                except Exception:
                    pass
                break

        workloads.append({
            "pod": pod.metadata.name, "namespace": ns, "phase": pod.status.phase,
            "gpu_requests": gpu_req,
            "owners": [{"kind": r.kind, "name": r.name} for r in owner_refs],
            "labels": dict(pod.metadata.labels or {}),
            "container_statuses": container_statuses,
            "sibling_pods": siblings[:20],
        })

    return json.dumps(workloads, indent=2, default=str) if workloads else "No GPU workloads found."


async def get_workload_logs(node_name: str, tail_lines: int = 200) -> str:
    api = get_core_api()
    pods = api.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
    system_ns = {"kube-system", "monitoring", "kube-node-lease", "kube-public"}
    error_patterns = [
        "nccl", "cuda error", "cuda_error", "torch.distributed", "runtimeerror",
        "traceback", "nvrm", "xid", "ecc", "fallen off", "sigterm", "sigkill",
        "oom", "out of memory", "failed", "error",
    ]

    results = {}
    for pod in pods.items:
        ns = pod.metadata.namespace
        if ns in system_ns:
            continue
        if any(r.kind == "DaemonSet" for r in (pod.metadata.owner_references or [])):
            continue
        has_gpu = any(
            "nvidia.com/gpu" in ((c.resources.requests or {}) if c.resources else {})
            for c in (pod.spec.containers or [])
        )
        if not has_gpu:
            continue

        try:
            container = pod.spec.containers[0].name if pod.spec.containers else None
            if not container:
                continue
            logs = api.read_namespaced_pod_log(
                name=pod.metadata.name, namespace=ns, container=container,
                tail_lines=tail_lines, timestamps=True,
            )
            error_lines = [ln for ln in logs.split("\n") if any(p in ln.lower() for p in error_patterns)]
            if error_lines:
                results[f"{ns}/{pod.metadata.name}"] = {"error_lines": error_lines[-50:], "total": len(error_lines)}
            else:
                results[f"{ns}/{pod.metadata.name}"] = {"note": "no errors found", "tail": logs[-1000:]}
        except Exception as exc:
            results[f"{ns}/{pod.metadata.name}"] = f"error: {exc}"

        if len(results) >= 5:
            break

    return json.dumps(results, indent=2, default=str) if results else "No GPU workload pods found."


# ---------------------------------------------------------------------------
# Remediation tools
# ---------------------------------------------------------------------------

async def cordon_node(node_name: str) -> str:
    api = get_core_api()
    api.patch_node(node_name, {"spec": {"unschedulable": True}})
    logger.info("Cordoned node %s", node_name)
    return f"Cordoned node {node_name}"


async def drain_node(node_name: str) -> str:
    api = get_core_api()
    api.patch_node(node_name, {"spec": {"unschedulable": True}})

    pods = api.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
    evicted, skipped = 0, 0
    for pod in pods.items:
        if any(r.kind == "DaemonSet" for r in (pod.metadata.owner_references or [])):
            skipped += 1
            continue
        try:
            api.create_namespaced_pod_eviction(
                pod.metadata.name, pod.metadata.namespace,
                client.V1Eviction(
                    metadata=client.V1ObjectMeta(name=pod.metadata.name, namespace=pod.metadata.namespace),
                    delete_options=client.V1DeleteOptions(grace_period_seconds=30),
                ),
            )
            evicted += 1
        except client.ApiException as exc:
            logger.warning("Failed to evict %s/%s: %s", pod.metadata.namespace, pod.metadata.name, exc.reason)

    logger.info("Drained node %s: evicted=%d, skipped_daemonset=%d", node_name, evicted, skipped)
    return f"Drained node {node_name}: evicted {evicted} pods, skipped {skipped} DaemonSet pods"


async def taint_node(node_name: str, key: str, value: str, effect: str) -> str:
    if effect not in ("NoSchedule", "PreferNoSchedule", "NoExecute"):
        return f"Invalid effect: {effect}"
    api = get_core_api()
    node = api.read_node(node_name)
    taints = list(node.spec.taints or [])
    taints.append(client.V1Taint(key=key, value=value, effect=effect))
    api.patch_node(node_name, {"spec": {"taints": [t.to_dict() for t in taints]}})
    logger.info("Tainted node %s: %s=%s:%s", node_name, key, value, effect)
    return f"Tainted node {node_name}: {key}={value}:{effect}"
