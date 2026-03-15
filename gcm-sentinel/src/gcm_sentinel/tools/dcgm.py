# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Query dcgm-exporter directly on a node when Prometheus doesn't have DCGM metrics."""
from __future__ import annotations

import httpx

from gcm_sentinel.k8s import get_core_api


def _find_dcgm_pod_ip(node_name: str) -> str | None:
    """Find the dcgm-exporter pod IP running on a specific node."""
    api = get_core_api()
    pods = api.list_pod_for_all_namespaces(
        field_selector=f"spec.nodeName={node_name}",
        label_selector="app.kubernetes.io/name=dcgm-exporter",
    )
    if not pods.items:
        # Try broader match.
        pods = api.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
        for pod in pods.items:
            if "dcgm" in pod.metadata.name.lower():
                return pod.status.pod_ip
        return None
    return pods.items[0].status.pod_ip


def _parse_prometheus_text(text: str, metric_filter: str = "") -> dict[str, list[dict]]:
    """Parse Prometheus exposition format into {metric_name: [{labels, value}]}."""
    metrics: dict[str, list[dict]] = {}
    for line in text.strip().split("\n"):
        if line.startswith("#") or not line:
            continue
        if metric_filter and metric_filter not in line:
            continue
        # "METRIC_NAME{label=val,...} VALUE"
        if "{" in line:
            name_part, rest = line.split("{", 1)
            labels_str, value_str = rest.rsplit("}", 1)
            labels = {}
            for pair in labels_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    labels[k.strip()] = v.strip().strip('"')
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            name_part = parts[0]
            value_str = parts[1]
            labels = {}

        name = name_part.strip()
        try:
            value = float(value_str.strip())
        except ValueError:
            continue

        metrics.setdefault(name, []).append({"labels": labels, "value": value})
    return metrics


async def query_dcgm_direct(node_name: str, metric_filter: str = "") -> str:
    """Query dcgm-exporter directly on a node via its pod IP.

    Useful when Prometheus doesn't scrape dcgm-exporter (common on clusters
    where DCGM metrics go through OTel instead).
    """
    import json

    pod_ip = _find_dcgm_pod_ip(node_name)
    if not pod_ip:
        return f"No dcgm-exporter pod found on node {node_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://{pod_ip}:9400/metrics")
            resp.raise_for_status()
        except Exception as exc:
            return f"Failed to query dcgm-exporter at {pod_ip}:9400: {exc}"

    metrics = _parse_prometheus_text(resp.text, metric_filter)

    # If no filter, summarize key metrics only (full output is too large).
    if not metric_filter:
        key_metrics = [
            "DCGM_FI_DEV_GPU_TEMP", "DCGM_FI_DEV_MEMORY_TEMP",
            "DCGM_FI_DEV_POWER_USAGE", "DCGM_FI_DEV_GPU_UTIL",
            "DCGM_FI_DEV_SM_CLOCK", "DCGM_FI_DEV_FB_USED",
            "DCGM_FI_DEV_ECC_SBE_VOL_TOTAL", "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL",
            "DCGM_FI_DEV_ECC_SBE_AGG_TOTAL", "DCGM_FI_DEV_ECC_DBE_AGG_TOTAL",
            "DCGM_FI_DEV_RETIRED_SBE", "DCGM_FI_DEV_RETIRED_DBE",
            "DCGM_FI_DEV_RETIRED_PENDING",
            "DCGM_FI_DEV_XID_ERRORS", "DCGM_FI_DEV_PCIE_REPLAY_COUNTER",
            "DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_COUNT_TOTAL",
            "DCGM_FI_DEV_THERMAL_VIOLATION", "DCGM_FI_DEV_PSTATE",
        ]
        metrics = {k: v for k, v in metrics.items() if k in key_metrics}

    text = json.dumps(metrics, indent=2)
    return text
