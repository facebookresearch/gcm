# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import json
import time

import httpx


def _parse_duration(duration: str) -> float:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if duration and duration[-1].lower() in units:
        try:
            return float(duration[:-1]) * units[duration[-1].lower()]
        except ValueError:
            pass
    try:
        return float(duration)
    except (ValueError, TypeError):
        return 300.0


async def query_prometheus(prometheus_url: str, query: str, duration: str = "5m") -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{prometheus_url}/api/v1/query",
            params={"query": query, "timeout": "15s"},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            return f"Prometheus query failed: {data}"

        if not data.get("data", {}).get("result"):
            duration_seconds = _parse_duration(duration)
            now = time.time()
            resp = await client.get(
                f"{prometheus_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": str(now - duration_seconds),
                    "end": str(now),
                    "step": "60s",
                    "timeout": "15s",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return json.dumps(data.get("data", {}), indent=2)


async def query_alertmanager(alertmanager_url: str, node_name: str = "") -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{alertmanager_url}/api/v2/alerts")
            resp.raise_for_status()
            alerts = resp.json()
        except Exception as exc:
            return f"Alertmanager query failed: {exc}"

    if node_name:
        node_labels = ("instance", "node", "nodename", "kubernetes_node")
        alerts = [
            a for a in alerts
            if any(node_name in str(a.get("labels", {}).get(k, "")) for k in node_labels)
        ]

    results = [
        {
            "alertname": a.get("labels", {}).get("alertname", ""),
            "severity": a.get("labels", {}).get("severity", ""),
            "state": a.get("status", {}).get("state", ""),
            "labels": a.get("labels", {}),
            "startsAt": a.get("startsAt", ""),
            "summary": a.get("annotations", {}).get("summary", ""),
            "description": a.get("annotations", {}).get("description", "")[:300],
        }
        for a in alerts[:30]
    ]

    return json.dumps(results, indent=2) if results else "No firing alerts found."
