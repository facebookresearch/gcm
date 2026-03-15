# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.gcm import get_gcm_health


class GCMHealthDataSource(DataSource):
    name = "gcm_health"

    def get_tools(self):
        return [{
            "name": "get_gcm_health",
            "description": "NPD health: problem_gauge/counter metrics + Gcm/NPD node conditions.",
            "input_schema": {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]},
        }]

    async def execute(self, tool_name, tool_input):
        return await get_gcm_health(tool_input["node_name"], self.cfg.prometheus_url)
