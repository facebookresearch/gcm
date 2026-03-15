# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Query node-exporter and InfiniBand metrics directly on nodes."""
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.node_exporter import query_infiniband_direct, query_node_exporter_direct

_NODE_SCHEMA = {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]}


class NodeDirectDataSource(DataSource):
    name = "node_direct"

    def get_tools(self):
        return [
            {
                "name": "query_node_exporter_direct",
                "description": (
                    "Query host metrics directly from node-exporter on a node. "
                    "Returns CPU, memory, temps, disk, and network stats. "
                    "Use metric_filter to narrow (e.g. 'hwmon_temp', 'load', 'infiniband')."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_name": {"type": "string"},
                        "metric_filter": {"type": "string", "description": "Substring filter", "default": ""},
                    },
                    "required": ["node_name"],
                },
            },
            {
                "name": "query_infiniband_direct",
                "description": (
                    "Query InfiniBand port metrics directly from node-exporter. "
                    "Shows IB link errors, data counters, and port status. "
                    "Falls back to general network error metrics if no IB found."
                ),
                "input_schema": _NODE_SCHEMA,
            },
        ]

    async def execute(self, tool_name, tool_input):
        if tool_name == "query_node_exporter_direct":
            return await query_node_exporter_direct(tool_input["node_name"], tool_input.get("metric_filter", ""))
        elif tool_name == "query_infiniband_direct":
            return await query_infiniband_direct(tool_input["node_name"])
        return f"Unknown tool: {tool_name}"
