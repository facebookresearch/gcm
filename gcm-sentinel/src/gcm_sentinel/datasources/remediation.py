# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Only registered when action_mode="execute". Tools are absent from
the LLM's schema in recommend/annotate modes.

All safety checks enforced HERE, before the K8s API call:
- Rate limiting
- Node name validation (can only act on the node being investigated)
- Node name validation (can only act on the node being investigated)
"""
from __future__ import annotations

import logging
import time
from collections import deque

from gcm_sentinel.datasources import DataSource
from gcm_sentinel.tools.kubernetes import cordon_node, drain_node, taint_node

logger = logging.getLogger(__name__)


class RemediationDataSource(DataSource):
    name = "remediation"

    def __init__(self, cfg):
        super().__init__(cfg)
        self._action_timestamps: deque[float] = deque()
        self._allowed_node: str | None = None  # Set by the engine before each investigation.

    def is_available(self):
        return self.cfg.can_execute

    def set_allowed_node(self, node_name: str) -> None:
        """Restrict remediation to a specific node. Called by the engine."""
        self._allowed_node = node_name

    def _is_rate_limited(self) -> bool:
        now = time.monotonic()
        while self._action_timestamps and (now - self._action_timestamps[0]) > 3600:
            self._action_timestamps.popleft()
        return len(self._action_timestamps) >= self.cfg.max_actions_per_hour

    def get_tools(self):
        return [
            {
                "name": "cordon_node",
                "description": "Mark node unschedulable. Only for confirmed hardware issues.",
                "input_schema": {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]},
            },
            {
                "name": "drain_node",
                "description": "Evict all non-DaemonSet pods + cordon. Only for critical hardware failures.",
                "input_schema": {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]},
            },
            {
                "name": "taint_node",
                "description": "Add a taint to a node.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "node_name": {"type": "string"},
                        "key": {"type": "string"}, "value": {"type": "string"},
                        "effect": {"type": "string", "enum": ["NoSchedule", "PreferNoSchedule", "NoExecute"]},
                    },
                    "required": ["node_name", "key", "value", "effect"],
                },
            },
        ]

    async def execute(self, tool_name, tool_input):
        target_node = tool_input.get("node_name", "")

        # Guard: only allow actions on the node being investigated.
        if self._allowed_node and target_node != self._allowed_node:
            msg = (
                f"BLOCKED: {tool_name} rejected — target node '{target_node}' does not match "
                f"the node being investigated ('{self._allowed_node}'). "
                f"You can only remediate the node you are investigating."
            )
            logger.warning(msg)
            return msg

        # Guard: rate limit.
        if self._is_rate_limited():
            msg = (
                f"RATE LIMITED: {tool_name} blocked. "
                f"{self.cfg.max_actions_per_hour} remediation actions per hour limit reached. "
                f"Include this action in your recommended_action assessment instead."
            )
            logger.warning(msg)
            return msg

        # Execute.
        if tool_name == "cordon_node":
            result = await cordon_node(target_node)
        elif tool_name == "drain_node":
            result = await drain_node(target_node)
        elif tool_name == "taint_node":
            result = await taint_node(target_node, tool_input["key"], tool_input["value"], tool_input["effect"])
        else:
            return f"Unknown tool: {tool_name}"

        self._action_timestamps.append(time.monotonic())
        logger.info("Remediation action %s executed on %s (%d/%d this hour)",
                     tool_name, target_node, len(self._action_timestamps), self.cfg.max_actions_per_hour)
        return result
