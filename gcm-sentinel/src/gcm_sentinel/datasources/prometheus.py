# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.prometheus import query_prometheus


class PrometheusDataSource(DataSource):
    name = "prometheus"

    def get_tools(self):
        return [{
            "name": "query_prometheus",
            "description": (
                "Execute a PromQL query against the cluster's Prometheus server. "
                "Common metric prefixes: DCGM_FI_DEV_* (GPU), node_* (host), "
                "kube_* (K8s state), problem_* (NPD). "
                "Filter by node with {instance=~\"NODE.*\"}, by GPU with {gpu=\"IDX\"}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "PromQL expression"},
                    "duration": {"type": "string", "description": "Range fallback (e.g. '5m')", "default": "5m"},
                },
                "required": ["query"],
            },
        }]

    async def execute(self, tool_name, tool_input):
        return await query_prometheus(self.cfg.prometheus_url, tool_input["query"], tool_input.get("duration", "5m"))
