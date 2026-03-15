# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Query dcgm-exporter directly on GPU nodes.

Falls back gracefully — if dcgm-exporter isn't running on a node,
the tool returns a clear message and the LLM uses other data sources.
"""
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.dcgm import query_dcgm_direct


class DCGMDirectDataSource(DataSource):
    name = "dcgm_direct"

    def get_tools(self):
        return [{
            "name": "query_dcgm_direct",
            "description": (
                "Query GPU metrics directly from the dcgm-exporter pod running on a node. "
                "Use this when Prometheus doesn't have DCGM metrics, or to get the latest "
                "real-time GPU data. Optionally filter by metric name substring."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_name": {"type": "string", "description": "Kubernetes node name"},
                    "metric_filter": {
                        "type": "string",
                        "description": "Only return metrics containing this substring (e.g. 'ECC', 'TEMP', 'XID'). Empty for key metrics summary.",
                        "default": "",
                    },
                },
                "required": ["node_name"],
            },
        }]

    async def execute(self, tool_name, tool_input):
        return await query_dcgm_direct(tool_input["node_name"], tool_input.get("metric_filter", ""))
