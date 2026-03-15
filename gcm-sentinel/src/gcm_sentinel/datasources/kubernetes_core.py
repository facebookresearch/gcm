# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.kubernetes import get_node_events, get_node_info, get_pod_logs

_NODE_SCHEMA = {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]}


class KubernetesCoreDataSource(DataSource):
    name = "kubernetes_core"

    def get_tools(self):
        return [
            {"name": "get_node_info", "description": "Node conditions, taints, labels, annotations, resources, pods.", "input_schema": _NODE_SCHEMA},
            {"name": "get_node_events", "description": "Recent K8s Events on the node (warnings, errors, investigation history).", "input_schema": _NODE_SCHEMA},
            {
                "name": "get_pod_logs",
                "description": "Logs from monitoring pods (dcgm, NPD, GCM). Use pod_name_pattern to filter.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_name": {"type": "string"},
                        "pod_name_pattern": {"type": "string", "default": ""},
                        "tail_lines": {"type": "integer", "default": 100},
                    },
                    "required": ["node_name"],
                },
            },
        ]

    async def execute(self, tool_name, tool_input):
        if tool_name == "get_node_info":
            return await get_node_info(tool_input["node_name"])
        elif tool_name == "get_node_events":
            return await get_node_events(tool_input["node_name"])
        elif tool_name == "get_pod_logs":
            return await get_pod_logs(tool_input["node_name"], tool_input.get("pod_name_pattern", ""), tool_input.get("tail_lines", 100))
        return f"Unknown tool: {tool_name}"
