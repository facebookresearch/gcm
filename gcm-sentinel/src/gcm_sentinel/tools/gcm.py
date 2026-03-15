# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import json

import httpx

from gcm_sentinel.k8s import get_core_api


async def get_gcm_health(node_name: str, prometheus_url: str) -> str:
    """NPD health: problem_gauge/counter metrics + Gcm/NPD node conditions."""
    health: dict = {"node": node_name, "npd_metrics": {}, "conditions": []}

    npd_queries = {
        "problem_gauge": f'problem_gauge{{instance=~"{node_name}.*"}}',
        "problem_counter": f'problem_counter{{instance=~"{node_name}.*"}}',
    }

    async with httpx.AsyncClient(timeout=15.0) as http:
        for key, query in npd_queries.items():
            try:
                resp = await http.get(
                    f"{prometheus_url}/api/v1/query",
                    params={"query": query},
                )
                resp.raise_for_status()
                health["npd_metrics"][key] = resp.json().get("data", {}).get("result", [])
            except Exception as exc:
                health["npd_metrics"][key] = f"error: {exc}"

    try:
        api = get_core_api()
        node = api.read_node(node_name)
        for cond in node.status.conditions or []:
            if cond.type.startswith(("Gcm", "NPD")):
                health["conditions"].append({
                    "type": cond.type,
                    "status": cond.status,
                    "reason": cond.reason or "",
                    "message": cond.message or "",
                    "lastTransitionTime": str(cond.last_transition_time),
                })
    except Exception as exc:
        health["conditions_error"] = str(exc)

    text = json.dumps(health, indent=2, default=str)
    return text
