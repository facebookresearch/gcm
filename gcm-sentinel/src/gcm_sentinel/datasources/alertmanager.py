# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.prometheus import query_alertmanager


class AlertmanagerDataSource(DataSource):
    name = "alertmanager"

    def is_available(self):
        return bool(self.cfg.alertmanager_url)

    def get_tools(self):
        return [{
            "name": "query_alertmanager",
            "description": "Currently firing Alertmanager alerts, optionally filtered by node.",
            "input_schema": {
                "type": "object",
                "properties": {"node_name": {"type": "string", "default": ""}},
                "required": [],
            },
        }]

    async def execute(self, tool_name, tool_input):
        return await query_alertmanager(self.cfg.alertmanager_url, tool_input.get("node_name", ""))
