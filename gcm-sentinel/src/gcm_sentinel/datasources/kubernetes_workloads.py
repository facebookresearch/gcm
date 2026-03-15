# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.kubernetes import get_workload_info, get_workload_logs


class KubernetesWorkloadsDataSource(DataSource):
    name = "kubernetes_workloads"

    def get_tools(self):
        return [
            {
                "name": "get_workload_info",
                "description": "GPU workload identity: job owner, labels, GPU requests, container status, sibling pods.",
                "input_schema": {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]},
            },
            {
                "name": "get_workload_logs",
                "description": "Error logs from GPU workload pods (NCCL, CUDA, XID, OOM patterns).",
                "input_schema": {
                    "type": "object",
                    "properties": {"node_name": {"type": "string"}, "tail_lines": {"type": "integer", "default": 200}},
                    "required": ["node_name"],
                },
            },
        ]

    async def execute(self, tool_name, tool_input):
        if tool_name == "get_workload_info":
            return await get_workload_info(tool_input["node_name"])
        elif tool_name == "get_workload_logs":
            return await get_workload_logs(tool_input["node_name"], tool_input.get("tail_lines", 200))
        return f"Unknown tool: {tool_name}"
