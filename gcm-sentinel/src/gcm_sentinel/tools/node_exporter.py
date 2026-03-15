# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Query node-exporter directly on a node."""
from __future__ import annotations

import json

import httpx

from gcm_sentinel.k8s import get_core_api
from gcm_sentinel.tools.dcgm import _parse_prometheus_text


def _find_node_exporter_ip(node_name: str) -> str | None:
    api = get_core_api()
    pods = api.list_pod_for_all_namespaces(
        field_selector=f"spec.nodeName={node_name}",
    )
    for pod in pods.items:
        name = pod.metadata.name.lower()
        if "node-exporter" in name or "node_exporter" in name:
            return pod.status.pod_ip
    return None


async def query_node_exporter_direct(node_name: str, metric_filter: str = "") -> str:
    """Query node-exporter directly on a node via its pod IP."""
    pod_ip = _find_node_exporter_ip(node_name)
    if not pod_ip:
        return f"No node-exporter pod found on node {node_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://{pod_ip}:9100/metrics")
            resp.raise_for_status()
        except Exception as exc:
            return f"Failed to query node-exporter at {pod_ip}:9100: {exc}"

    metrics = _parse_prometheus_text(resp.text, metric_filter)

    if not metric_filter:
        # Without a filter, return key host health metrics only.
        key_prefixes = [
            "node_hwmon_temp_celsius", "node_cpu_seconds_total",
            "node_memory_MemAvailable_bytes", "node_memory_MemTotal_bytes",
            "node_load1", "node_load5", "node_load15",
            "node_disk_io_time_seconds_total",
            "node_filesystem_avail_bytes",
            "node_infiniband",  # IB metrics if available.
            "node_network_receive_errs_total", "node_network_transmit_errs_total",
        ]
        metrics = {k: v for k, v in metrics.items() if any(k.startswith(p) for p in key_prefixes)}

    text = json.dumps(metrics, indent=2)
    return text


async def query_infiniband_direct(node_name: str) -> str:
    """Query InfiniBand/network metrics from node-exporter on a node."""
    pod_ip = _find_node_exporter_ip(node_name)
    if not pod_ip:
        return f"No node-exporter pod found on node {node_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://{pod_ip}:9100/metrics")
            resp.raise_for_status()
        except Exception as exc:
            return f"Failed to query node-exporter at {pod_ip}:9100: {exc}"

    metrics = _parse_prometheus_text(resp.text)
    ib_metrics = {k: v for k, v in metrics.items() if "infiniband" in k or "ib_" in k.lower()}

    if not ib_metrics:
        # Fall back to general network error metrics.
        ib_metrics = {k: v for k, v in metrics.items()
                      if k.startswith(("node_network_receive_errs", "node_network_transmit_errs",
                                       "node_network_receive_drop", "node_network_transmit_drop"))}
        if not ib_metrics:
            return "No InfiniBand or network error metrics found on this node."

    text = json.dumps(ib_metrics, indent=2)
    return text
